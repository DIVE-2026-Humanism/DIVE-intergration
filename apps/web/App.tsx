import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert, Animated, FlatList, Image, Linking, Modal, Platform, Pressable, SafeAreaView, ScrollView,
  StatusBar as RNStatusBar, StyleSheet, Switch, Text, TextInput, View,
} from 'react-native';
import { Feather, MaterialCommunityIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import * as ImagePicker from 'expo-image-picker';
import * as Print from 'expo-print';
import * as Sharing from 'expo-sharing';
import * as FileSystem from 'expo-file-system/legacy';
import { theme } from './src/config/theme';
import { createGonggu, getGongguDetail, getGongguList, prepareGongguPayment, toggleGongguLike, getMyLikedGonggus } from './src/api/gonggu';
import { getPolicyList, getPolicies, getPolicyCategories, getPolicyDetail, PolicyCategory, togglePolicyLike, getMyLikedPolicies, getTopPolicies } from './src/api/policy';
import { Gonggu, Policy, PolicyDetail as PolicyDetailData } from './src/types';
import { useKakaoAuth } from './src/auth/useKakaoAuth';
import { logout as apiLogout, restoreSession, submitOnboarding, updateMyProfile, Member } from './src/api/auth';
import { getNotifications, getUnreadCount, markAllNotificationsRead, NotificationItem, getNotificationSettings, updateNotificationSettings } from './src/api/notification';
import { getSearchHistory, addSearchHistory, removeSearchHistory, clearSearchHistory } from './src/api/search';
import { requestDiagnose, DiagnoseResult, getRecommendationProgress, RecommendationProgress, getSavedRecommendationResult, getSavedRecommendationResults, saveRecommendationResult, SavedRecommendationResultDetail, SavedRecommendationResultSummary } from './src/api/diagnose';
import { connectKcb } from './src/api/kcb';

const onboardingDone = (m: Member | null) => !!m && m.career !== '미입력' && m.finalEducation !== '미입력';

type Tab = 'home' | 'policy' | 'recommend' | 'gonggu' | 'my';
type FeatherName = React.ComponentProps<typeof Feather>['name'];

const navItems: { id: Exclude<Tab, 'recommend'>; label: string; icon: FeatherName }[] = [
  { id: 'home', label: '홈', icon: 'home' },
  { id: 'policy', label: '정책', icon: 'menu' },
  { id: 'gonggu', label: '공구', icon: 'shopping-cart' },
  { id: 'my', label: '마이', icon: 'user' },
];

export default function App() {
  const [tab, setTab] = useState<Tab>('home');
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [gonggus, setGonggus] = useState<Gonggu[]>([]);
  const [selectedPolicy, setSelectedPolicy] = useState<Policy | null>(null);
  const [selectedGonggu, setSelectedGonggu] = useState<Gonggu | null>(null);
  const [member, setMember] = useState<Member | null>(null);
  const [loggingIn, setLoggingIn] = useState(false);
  const [savedRec, setSavedRec] = useState<SavedRec | null>(null);
  const [dataReady, setDataReady] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);
  const [policyQuery, setPolicyQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const { signIn } = useKakaoAuth(
    (m) => { setMember(m); setLoggingIn(false); },
    (msg) => { setLoggingIn(false); Alert.alert('로그인 실패', msg); },
  );

  const loggedIn = !!member;
  const profileSaved = onboardingDone(member);

  const [likedGonggu, setLikedGonggu] = useState<Record<string, boolean>>({});

  const loadGonggus = useCallback(async () => {
    try {
      setGonggus(await getGongguList());
    } catch {
      // 기존 목록을 유지한다. 최초 조회 실패 시에는 빈 목록이 표시된다.
    }
  }, []);

  const loadLikedGonggu = useCallback(async () => {
    if (!member) { setLikedGonggu({}); return; }
    try {
      const likes = await getMyLikedGonggus();
      setLikedGonggu(Object.fromEntries(likes.map((g) => [g.id, true])));
    } catch {
      // 좋아요 상태 조회 실패 시 무시(빈 상태 유지)
    }
  }, [member]);

  const toggleGonggu = useCallback((id: string) => {
    if (!member) { Alert.alert('로그인이 필요해요', '공구 좋아요는 로그인 후 이용할 수 있어요.'); return; }
    setLikedGonggu((s) => ({ ...s, [id]: !s[id] })); // 낙관적 반영
    void toggleGongguLike(id).catch(() => {
      setLikedGonggu((s) => ({ ...s, [id]: !s[id] })); // 실패 시 롤백
    });
  }, [member]);

  useEffect(() => { void Promise.allSettled([getPolicyList().then(setPolicies), loadGonggus()]).finally(() => setDataReady(true)); }, [loadGonggus]);
  useEffect(() => { if (tab === 'gonggu') void loadGonggus(); }, [tab, loadGonggus]);
  useEffect(() => { void loadLikedGonggu(); }, [loadLikedGonggu]);
  useEffect(() => { void restoreSession().then((m) => { if (m) setMember(m); }).finally(() => setSessionReady(true)); }, []);

  const handleLogin = () => {
    if (loggingIn) return;
    setLoggingIn(true);
    signIn();
  };
  const handleOnboard = async (career: string, finalEducation: string) => { setMember(await submitOnboarding(career, finalEducation)); };
  const handleProfileUpdate = async (nickname: string, career: string, finalEducation: string) => { setMember(await updateMyProfile(nickname, career, finalEducation)); };
  const handleLogout = async () => {
    await apiLogout();
    setMember(null);
  };

  const renderPage = () => {
    if (searchOpen) return <SearchScreen loggedIn={loggedIn} onClose={() => setSearchOpen(false)} onSearch={(kw) => { setPolicyQuery(kw); setTab('policy'); setSearchOpen(false); }} />;
    if (selectedPolicy) return <PolicyDetail policy={selectedPolicy} onBack={() => setSelectedPolicy(null)} loggedIn={loggedIn} goLogin={() => { setSelectedPolicy(null); setTab('my'); }} />;
    if (selectedGonggu) return <GongguDetail item={selectedGonggu} onBack={() => setSelectedGonggu(null)} liked={!!likedGonggu[selectedGonggu.id]} onToggleLike={toggleGonggu} loggedIn={loggedIn} goLogin={() => { setSelectedGonggu(null); setTab('my'); }} />;
    switch (tab) {
      case 'home': return <Home policies={policies} gonggus={gonggus} openPolicy={setSelectedPolicy} openGonggu={setSelectedGonggu} setTab={setTab} loggedIn={loggedIn} onOpenSearch={() => setSearchOpen(true)} likedGonggu={likedGonggu} onToggleGonggu={toggleGonggu} />;
      case 'policy': return <PolicyList open={setSelectedPolicy} initialQuery={policyQuery} loggedIn={loggedIn} goLogin={() => setTab('my')} />;
      case 'recommend': return <Recommendation onSave={setSavedRec} loggedIn={loggedIn} goLogin={() => setTab('my')} />;
      case 'gonggu': return <GongguList items={gonggus} open={setSelectedGonggu} likedGonggu={likedGonggu} onToggleGonggu={toggleGonggu} loggedIn={loggedIn} goLogin={() => setTab('my')} onCreated={loadGonggus} />;
      case 'my': return <MyPage member={member} loggingIn={loggingIn} onLogin={handleLogin} onLogout={handleLogout} onOnboard={handleOnboard} onProfileUpdate={handleProfileUpdate} profileSaved={profileSaved} gonggus={gonggus} openGonggu={setSelectedGonggu} openPolicy={setSelectedPolicy} />;
    }
  };

  const showNav = !selectedPolicy && !selectedGonggu && !searchOpen;
  const booting = !dataReady || !sessionReady;

  if (booting) {
    return (
      <SafeAreaView style={styles.safe}>
        <StatusBar style="dark" />
        <AppSkeleton />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="dark" />
      {renderPage()}
      {showNav && (
        <View style={styles.tabBar}>
          <NavButton item={navItems[0]} active={tab === 'home'} onPress={() => setTab('home')} />
          <NavButton item={navItems[1]} active={tab === 'policy'} onPress={() => setTab('policy')} />
          <View style={styles.fabSlot} />
          <NavButton item={navItems[2]} active={tab === 'gonggu'} onPress={() => setTab('gonggu')} />
          <NavButton item={navItems[3]} active={tab === 'my'} onPress={() => setTab('my')} />
          <Pressable style={[styles.fab, tab === 'recommend' && styles.fabActive]} onPress={() => setTab('recommend')} accessibilityRole="tab" accessibilityState={{ selected: tab === 'recommend' }}>
            <MaterialCommunityIcons name="star-four-points" size={23} color="#fff" />
            <Text style={styles.fabLabel}>정책추천</Text>
          </Pressable>
        </View>
      )}
    </SafeAreaView>
  );
}

function SkelBox({ style }: { style?: any }) {
  const op = useState(() => new Animated.Value(0.5))[0];
  useEffect(() => {
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(op, { toValue: 1, duration: 700, useNativeDriver: true }),
      Animated.timing(op, { toValue: 0.5, duration: 700, useNativeDriver: true }),
    ]));
    loop.start();
    return () => loop.stop();
  }, []);
  return <Animated.View style={[styles.skelBox, { opacity: op }, style]} />;
}

/** 앱 부팅 중(세션 복구·초기 데이터 로딩) 표시하는 홈 형태의 스켈레톤 스플래시 */
function AppSkeleton() {
  return (
    <View style={styles.skelPage}>
      <SkelBox style={{ width: 130, height: 36, borderRadius: 8, alignSelf: 'center', marginTop: 24, marginBottom: 20 }} />
      <SkelBox style={{ height: 46, borderRadius: 24, marginBottom: 16 }} />
      <SkelBox style={{ width: 180, height: 16, marginBottom: 24 }} />
      <SkelBox style={{ width: 70, height: 20, marginBottom: 12 }} />
      <View style={{ flexDirection: 'row', gap: 12, marginBottom: 24 }}>
        <SkelBox style={{ width: 150, height: 200 }} />
        <SkelBox style={{ width: 150, height: 200 }} />
      </View>
      <SkelBox style={{ width: 70, height: 20, marginBottom: 12 }} />
      {[0, 1, 2].map((i) => <SkelBox key={i} style={{ height: 66, marginBottom: 10 }} />)}
    </View>
  );
}

function SearchScreen({ loggedIn, onClose, onSearch }: { loggedIn: boolean; onClose: () => void; onSearch: (kw: string) => void }) {
  const [q, setQ] = useState('');
  const [history, setHistory] = useState<string[]>([]);

  useEffect(() => {
    if (!loggedIn) { setHistory([]); return; }
    getSearchHistory().then(setHistory).catch(() => {});
  }, [loggedIn]);

  const submit = (kw: string) => {
    const k = kw.trim();
    if (!k) return;
    if (loggedIn) addSearchHistory(k).catch(() => {});
    onSearch(k);
  };
  const removeOne = (kw: string) => {
    setHistory((h) => h.filter((x) => x !== kw));
    if (loggedIn) removeSearchHistory(kw).catch(() => {});
  };
  const clearAll = () => {
    setHistory([]);
    if (loggedIn) clearSearchHistory().catch(() => {});
  };

  return (
    <View style={styles.flex}>
      <View style={styles.searchTopRow}>
        <Pressable onPress={onClose} hitSlop={10}><Feather name="chevron-left" size={26} color={theme.text} /></Pressable>
        <View style={styles.searchBox}>
          <Feather name="search" size={18} color={theme.textMuted} />
          <TextInput
            value={q}
            onChangeText={setQ}
            placeholder="기업, 공고, 콘텐츠 검색"
            placeholderTextColor={theme.textFaint}
            style={styles.searchBoxInput}
            autoFocus
            returnKeyType="search"
            onSubmitEditing={() => submit(q)}
          />
        </View>
      </View>

      <View style={styles.recentHead}>
        <Text style={styles.recentTitle}>최근 검색어</Text>
        {history.length > 0 && <Pressable onPress={clearAll} hitSlop={8}><Text style={styles.recentClear}>전체 삭제</Text></Pressable>}
      </View>

      {history.length === 0 ? (
        <Text style={styles.recentEmpty}>{loggedIn ? '최근 검색어가 없어요' : '로그인하면 검색 이력이 저장돼요'}</Text>
      ) : (
        <View style={styles.recentWrap}>
          {history.map((kw) => (
            <View key={kw} style={styles.recentChip}>
              <Pressable onPress={() => submit(kw)} hitSlop={4}><Text style={styles.recentChipText}>{kw}</Text></Pressable>
              <Pressable onPress={() => removeOne(kw)} hitSlop={8}><Feather name="x" size={14} color={theme.textFaint} /></Pressable>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

function NavButton({ item, active, onPress }: { item: { label: string; icon: FeatherName }; active: boolean; onPress: () => void }) {
  const color = active ? theme.text : '#8C9CA6';
  return (
    <Pressable style={styles.nav} onPress={onPress} accessibilityRole="tab" accessibilityState={{ selected: active }}>
      <Feather name={item.icon} size={20} color={color} />
      <Text style={[styles.navLabel, { color, fontWeight: active ? '700' : '500' }]}>{item.label}</Text>
    </Pressable>
  );
}

function Home({ policies, gonggus, openPolicy, openGonggu, setTab, loggedIn, onOpenSearch, likedGonggu, onToggleGonggu }: { policies: Policy[]; gonggus: Gonggu[]; openPolicy: (p: Policy) => void; openGonggu: (g: Gonggu) => void; setTab: (t: Tab) => void; loggedIn: boolean; onOpenSearch: () => void; likedGonggu: Record<string, boolean>; onToggleGonggu: (id: string) => void }) {
  const [rank, setRank] = useState(0);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifs, setNotifs] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [rankingOpen, setRankingOpen] = useState(false);
  const words = ['부산 청년정책 지원금', '이력서 첨삭 무료체험', '공공기관 채용공고', '부산 창업지원센터', '청년 월세지원 신청', '인턴십 채용 정보'];
  const [topTitles, setTopTitles] = useState<string[]>([]);
  const [topPolicyIds, setTopPolicyIds] = useState<number[]>([]);
  // 실시간 인기 Top10을 1분마다 폴링. topPolicies는 policyId만 주므로 로드된 정책 목록으로 제목 매핑.
  useEffect(() => {
    let alive = true;
    const load = () => {
      getTopPolicies()
        .then((ids) => {
          if (!alive) return;
          setTopPolicyIds(ids);
          const titles = ids
            .map((id) => policies.find((p) => p.id === String(id))?.title)
            .filter((t): t is string => !!t);
          setTopTitles(titles);
        })
        .catch(() => {});
    };
    load();
    const poll = setInterval(load, 60_000);
    return () => { alive = false; clearInterval(poll); };
  }, [policies]);

  const ticker = topTitles.length ? topTitles : words;
  const tickerIdx = rank % ticker.length;
  const topPolicies = useMemo(() => {
    const ranked = topPolicyIds
      .map((id) => policies.find((policy) => policy.id === String(id)))
      .filter((policy): policy is Policy => !!policy);
    return (ranked.length ? ranked : [...policies].sort((a, b) => b.popularity - a.popularity)).slice(0, 10);
  }, [policies, topPolicyIds]);
  useEffect(() => { const timer = setInterval(() => setRank((n) => n + 1), 2200); return () => clearInterval(timer); }, []);

  const loadNotifs = useCallback(() => {
    if (!loggedIn) { setNotifs([]); setUnread(0); return; }
    getNotifications().then(setNotifs).catch(() => {});
    getUnreadCount().then(setUnread).catch(() => {});
  }, [loggedIn]);
  useEffect(() => {
    loadNotifs();
    const poll = setInterval(loadNotifs, 30_000);
    return () => clearInterval(poll);
  }, [loadNotifs]);

  const toggleNotif = () => {
    const next = !notifOpen;
    setNotifOpen(next);
    if (next && loggedIn) {
      loadNotifs();
      if (unread > 0) markAllNotificationsRead().then(() => setUnread(0)).catch(() => {});
    }
  };

  return (
    <View style={styles.flex}>
      <ScrollView contentContainerStyle={styles.homeScroll} showsVerticalScrollIndicator={false}>
        <LinearGradient colors={[theme.headerTop, theme.background]} style={styles.header}>
          <View style={styles.headerTopRow}>
            <Pressable onPress={toggleNotif} hitSlop={10} style={styles.bellWrap}>
              <Feather name="bell" size={21} color={theme.text} />
              {unread > 0 && <View style={styles.bellDot} />}
            </Pressable>
          </View>
          <Image source={require('./assets/main_logo.png')} style={styles.logoImg} resizeMode="contain" />

          <Pressable style={styles.search} onPress={onOpenSearch}>
            <Feather name="search" size={17} color={theme.textMuted} />
            <Text style={styles.searchPlaceholder}>정책 검색</Text>
          </Pressable>
          <Pressable style={styles.ranking} onPress={() => setRankingOpen(true)} accessibilityRole="button" accessibilityLabel="실시간 인기 정책 10개 보기">
            <Text style={styles.rankNum}>{tickerIdx + 1}</Text>
            <Text numberOfLines={1} style={styles.rankText}>{ticker[tickerIdx]}</Text>
            <Feather name="chevron-down" size={15} color="#8C9CA6" />
          </Pressable>
        </LinearGradient>

        <View style={styles.section}>
          <View style={styles.sectionHead}>
            <Text style={styles.sectionTitle}>공구</Text>
            <Text style={styles.hint}>가로로 넘겨보세요 →</Text>
          </View>
          <FlatList
            horizontal
            showsHorizontalScrollIndicator={false}
            data={gonggus}
            keyExtractor={(x) => x.id}
            contentContainerStyle={styles.carousel}
            renderItem={({ item }) => <GongguCard item={item} onPress={() => openGonggu(item)} liked={!!likedGonggu[item.id]} onToggleLike={onToggleGonggu} />}
            ListFooterComponent={<MoreCard onPress={() => setTab('gonggu')} />}
          />
        </View>

        <View style={[styles.section, styles.policySection]}>
          <View style={styles.sectionHead}>
            <Text style={styles.sectionTitle}>정책</Text>
            <Pressable style={styles.pill} onPress={() => setTab('policy')}>
              <Text style={styles.pillText}>전체보기 ›</Text>
            </Pressable>
          </View>
          {policies.slice(0, 3).map((p, i) => (
            <Pressable key={p.id} onPress={() => openPolicy(p)} style={[styles.policyRow, i < 2 && styles.policyRowDivider]}>
              <View style={styles.tag}><Text style={styles.tagText}>{p.category}</Text></View>
              <Text style={styles.policyRowTitle}>{p.title}</Text>
              <Text numberOfLines={2} ellipsizeMode="tail" style={styles.policyRowDesc}>{p.benefit}</Text>
              <Text style={styles.policyRowMore}>자세히보기 ›</Text>
            </Pressable>
          ))}
        </View>
      </ScrollView>

      <Modal transparent visible={rankingOpen} animationType="fade" onRequestClose={() => setRankingOpen(false)}>
        <Pressable style={styles.rankingModalDim} onPress={() => setRankingOpen(false)}>
          <Pressable style={styles.rankingModalCard} onPress={() => {}}>
            <View style={styles.rankingModalHead}>
              <View><Text style={styles.rankingModalTitle}>실시간 인기 정책 TOP 10</Text><Text style={styles.rankingModalSub}>좋아요가 많은 순으로 보여드려요</Text></View>
              <Pressable onPress={() => setRankingOpen(false)} hitSlop={10} accessibilityLabel="실시간 인기 정책 닫기"><Feather name="x" size={22} color={theme.text} /></Pressable>
            </View>
            <ScrollView style={styles.rankingModalList} showsVerticalScrollIndicator={false}>
              {topPolicies.map((policy, index) => (
                <Pressable key={policy.id} onPress={() => { setRankingOpen(false); openPolicy(policy); }} style={styles.rankingPolicyRow}>
                  <Text style={styles.rankingPolicyNumber}>{index + 1}</Text>
                  <View style={styles.rankingPolicyCopy}>
                    <Text numberOfLines={1} style={styles.rankingPolicyTitle}>{policy.title}</Text>
                    <Text numberOfLines={1} style={styles.rankingPolicyMeta}>{policy.category} · 좋아요 인기 정책</Text>
                  </View>
                  <Feather name="chevron-right" size={18} color={theme.textFaint} />
                </Pressable>
              ))}
              {topPolicies.length === 0 && <Text style={styles.rankingEmpty}>인기 정책을 불러오는 중입니다.</Text>}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>

      {notifOpen && (
        <>
          <Pressable style={styles.notifBackdrop} onPress={() => setNotifOpen(false)} />
          <View style={styles.notifPanel}>
            <Text style={styles.notifHead}>알림</Text>
            {!loggedIn ? (
              <View style={styles.notifEmpty}><Text style={styles.notifBody}>로그인하면 알림을 확인할 수 있어요</Text></View>
            ) : notifs.length === 0 ? (
              <View style={styles.notifEmpty}><Text style={styles.notifBody}>새로운 알림이 없어요</Text></View>
            ) : (
              <ScrollView style={styles.notifList} showsVerticalScrollIndicator={false}>
                {notifs.map((n, i) => (
                  <NotifItem key={n.id} title={n.title} body={n.body} time={relativeTime(n.createdAt)} muted={n.type === 'policy'} last={i === notifs.length - 1} />
                ))}
              </ScrollView>
            )}
          </View>
        </>
      )}
    </View>
  );
}

function relativeTime(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '';
  const m = Math.floor((Date.now() - t) / 60000);
  if (m < 1) return '방금 전';
  if (m < 60) return `${m}분 전`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}시간 전`;
  const d = Math.floor(h / 24);
  if (d === 1) return '어제';
  if (d < 7) return `${d}일 전`;
  return iso.slice(0, 10);
}

function NotifItem({ title, body, time, muted, last }: { title: string; body: string; time: string; muted?: boolean; last?: boolean }) {
  return (
    <View style={[styles.notifItem, last && styles.notifItemLast]}>
      <Text style={[styles.notifTitle, muted && styles.notifTitleMuted]}>{title}</Text>
      <Text style={styles.notifBody}>{body}</Text>
      <Text style={styles.notifTime}>{time}</Text>
    </View>
  );
}

function GongguCard({ item, onPress, wide = false, liked, onToggleLike }: { item: Gonggu; onPress: () => void; wide?: boolean; liked?: boolean; onToggleLike?: (id: string) => void }) {
  return (
    <Pressable onPress={onPress} style={[styles.gongguCard, wide && styles.gongguWide]}>
      <LinearGradient colors={[theme.cardImgA, theme.cardImgB]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[styles.gongguImg, wide && styles.gongguImgWide]}>
        {item.imageUrl && <Image source={{ uri: item.imageUrl }} style={styles.gongguRemoteImage} resizeMode="cover" />}
        {onToggleLike ? (
          <Pressable onPress={() => onToggleLike(item.id)} hitSlop={10} style={styles.gongguHeart}>
            <MaterialCommunityIcons name={liked ? 'heart' : 'heart-outline'} size={20} color={liked ? theme.accent : '#fff'} />
          </Pressable>
        ) : (
          <Feather name="heart" size={17} color="#fff" style={styles.heart} />
        )}
      </LinearGradient>
      <Text style={styles.brand}>{item.brand}</Text>
      <Text numberOfLines={2} style={styles.gongguName}>{item.name}</Text>
      {!!item.writerNickname && <Text style={styles.gongguWriter}>작성자 {item.writerNickname}</Text>}
      <Text style={styles.gongguMeta}>{item.deadline} · {item.amount}</Text>
      <Text style={styles.percent}>{item.currentCount ?? 0}/{item.targetCount ?? 0}명 · {item.percent}% 달성</Text>
    </Pressable>
  );
}

function MoreCard({ onPress }: { onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={styles.moreCard}>
      <Feather name="plus" size={26} color={theme.text} />
      <Text style={styles.moreTitle}>더보기</Text>
      <Text style={styles.moreSub}>공구 탭으로</Text>
    </Pressable>
  );
}

const POLICY_SORTS: { key: 'default' | 'popular'; label: string }[] = [
  { key: 'default', label: '기본' }, { key: 'popular', label: '인기순' },
];

function PolicyList({ open, initialQuery, loggedIn, goLogin }: { open: (p: Policy) => void; initialQuery: string; loggedIn: boolean; goLogin: () => void }) {
  const [cats, setCats] = useState<PolicyCategory[]>([]);
  const [applied, setApplied] = useState<string | null>(null); // 적용된 대분류 (null=전체)
  const [list, setList] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [sortKey, setSortKey] = useState<'default' | 'popular'>('default');
  const [query, setQuery] = useState(initialQuery);
  const [saved, setSaved] = useState<Record<string, boolean>>({});

  useEffect(() => { setQuery(initialQuery); }, [initialQuery]);
  useEffect(() => { getPolicyCategories().then(setCats).catch(() => {}); }, []);
  // 로그인 시 내가 좋아요한 정책을 북마크 초기 상태로 반영
  useEffect(() => {
    if (!loggedIn) { setSaved({}); return; }
    getMyLikedPolicies().then((likes) => setSaved(Object.fromEntries(likes.map((p) => [p.id, true])))).catch(() => {});
  }, [loggedIn]);

  const toggleLike = (id: string) => {
    if (!loggedIn) {
      Alert.alert('로그인 필요', '관심 정책은 로그인 후 이용할 수 있어요.', [{ text: '취소', style: 'cancel' }, { text: '로그인', onPress: goLogin }]);
      return;
    }
    const next = !saved[id];
    setSaved((s) => ({ ...s, [id]: next })); // 낙관적 반영
    togglePolicyLike(id).catch(() => {
      setSaved((s) => ({ ...s, [id]: !next })); // 실패 시 롤백
      Alert.alert('실패', '관심 정책 저장에 실패했어요.');
    });
  };
  // 대분류/키워드 변경 시 서버 검색 (300ms 디바운스)
  useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => {
      getPolicies(applied, null, query.trim() || null).then(setList).catch(() => setList([])).finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(t);
  }, [applied, query]);

  const view = useMemo(() => {
    const arr = [...list];
    if (sortKey === 'popular') arr.sort((a, b) => b.popularity - a.popularity);
    return arr;
  }, [list, sortKey]);

  return (
    <View style={styles.flex}>
      <View style={styles.polHeader}>
        <Text style={styles.polTitle}>정책</Text>
        <View style={styles.search}>
          <Feather name="search" size={17} color={theme.textMuted} />
          <TextInput value={query} onChangeText={setQuery} placeholder="정책명, 키워드 검색 (예: 월세지원)" placeholderTextColor={theme.textMuted} style={styles.searchInput} />
        </View>
        <Pressable style={styles.filterBtn} onPress={() => setSheetOpen(true)}>
          <Feather name="sliders" size={15} color={theme.accent} />
          <Text style={styles.filterBtnText}>{applied ?? '전체 분야'}</Text>
          <Feather name="chevron-down" size={16} color={theme.textMuted} style={{ marginLeft: 'auto' }} />
        </Pressable>
        <View style={styles.polMetaRow}>
          <Text style={styles.polCount}>총 <Text style={styles.polCountNum}>{view.length}</Text>개의 정책이 있습니다</Text>
          <View style={styles.sortRow}>
            {POLICY_SORTS.map((s) => (
              <Pressable key={s.key} onPress={() => setSortKey(s.key)} style={[styles.sortChip, sortKey === s.key && styles.sortChipOn]}>
                <Text style={[styles.sortChipText, sortKey === s.key && styles.sortChipTextOn]}>{s.label}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      </View>

      {loading ? (
        <View style={styles.polListPad}><Skeleton delay={0} /><Skeleton delay={200} /><Skeleton delay={400} /></View>
      ) : view.length === 0 ? (
        <View style={styles.polEmpty}>
          <Text style={styles.polEmptyText}>조건에 맞는 정책이 없어요</Text>
          <Pressable onPress={() => { setApplied(null); setQuery(''); }} style={styles.resetBtn}><Text style={styles.resetBtnText}>필터 초기화</Text></Pressable>
        </View>
      ) : (
        <FlatList
          data={view}
          keyExtractor={(p) => p.id}
          contentContainerStyle={styles.polListPad}
          showsVerticalScrollIndicator={false}
          renderItem={({ item }) => {
            const isSaved = !!saved[item.id];
            return (
              <Pressable onPress={() => open(item)} style={styles.polItem}>
                <Pressable onPress={() => toggleLike(item.id)} style={styles.polBookmark} hitSlop={8}>
                  <MaterialCommunityIcons name={isSaved ? 'bookmark' : 'bookmark-outline'} size={18} color={isSaved ? theme.accent : '#8C9CA6'} />
                </Pressable>
                <View style={styles.tag}><Text style={styles.tagText}>{item.category}</Text></View>
                <Text style={styles.polItemTitle}>{item.title}</Text>
                <Text style={styles.polItemSummary}>{item.summary}</Text>
                <Text style={styles.polItemInstitution}>{item.institution} · {item.targetAge}</Text>
                <View style={styles.polItemBottom}>
                  <Text style={styles.polDeadline}>{item.deadline}</Text>
                  <Text style={styles.polItemMore}>자세히보기 ›</Text>
                </View>
              </Pressable>
            );
          }}
        />
      )}

      <FilterBottomSheet
        visible={sheetOpen}
        title="정책 분야"
        options={cats.map((c) => c.lclsfNm)}
        selected={applied}
        onApply={(sel) => { setApplied(sel); setSheetOpen(false); }}
        onDismiss={() => setSheetOpen(false)}
      />
    </View>
  );
}

/** 단일 선택 필터 바텀시트 (초기화/적용하기). 바깥 탭·닫기는 취소로 처리(적용 안 함). */
function FilterBottomSheet({ visible, title, options, selected, onApply, onDismiss }: { visible: boolean; title: string; options: string[]; selected: string | null; onApply: (sel: string | null) => void; onDismiss: () => void }) {
  const [draft, setDraft] = useState<string | null>(selected);
  useEffect(() => { if (visible) setDraft(selected); }, [visible, selected]);
  return (
    <Modal transparent visible={visible} animationType="slide" onRequestClose={onDismiss}>
      <Pressable style={styles.sheetDim} onPress={onDismiss}>
        <Pressable style={styles.sheet} onPress={() => {}}>
          <View style={styles.sheetHead}>
            <Text style={styles.sheetTitle}>{title}</Text>
            <Pressable style={styles.sheetReset} onPress={() => setDraft(null)} hitSlop={8}>
              <Feather name="refresh-ccw" size={13} color={theme.textMuted} />
              <Text style={styles.sheetResetText}>초기화</Text>
            </Pressable>
          </View>
          <ScrollView style={styles.sheetList} showsVerticalScrollIndicator={false}>
            {options.map((o) => {
              const on = o === draft;
              return (
                <Pressable key={o} onPress={() => setDraft(o)} style={[styles.sheetOption, on && styles.sheetOptionOn]} accessibilityRole="radio" accessibilityState={{ selected: on }}>
                  <Text style={[styles.sheetOptionText, on && styles.sheetOptionTextOn]}>{o}</Text>
                  {on && <Feather name="check" size={18} color={theme.accent} />}
                </Pressable>
              );
            })}
          </ScrollView>
          <View style={styles.sheetDivider} />
          <Pressable style={styles.sheetApply} onPress={() => onApply(draft)}>
            <Text style={styles.sheetApplyText}>적용하기</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

type RecStep = 'INTRO' | 'CAT' | 'A' | 'B' | 'C';
type RecPolicy = { id: number; title: string; tag: string; summary: string; reason: string; impact: 'up' | 'down'; impactText: string };
type SavedRec = { score: number; grade: string; policyIds: number[] };
type KcbConnection = { score: number; grade: string; updatedAt: string };

const MAJORS: { key: string; label: string; subs: string[] }[] = [
  { key: 'job', label: '일자리', subs: ['취업', '재직자', '창업'] },
  { key: 'housing', label: '주거', subs: ['주택 및 거주지', '기숙사', '전월세 및 주거급여 지원'] },
  { key: 'edu', label: '교육', subs: ['미래역량강화', '교육비지원', '온라인교육'] },
  { key: 'welfare', label: '복지문화', subs: ['취약계층 및 금융지원', '건강', '예술인지원', '문화활동'] },
  { key: 'rights', label: '참여권리', subs: ['청년참여', '정책인프라구축', '청년국제교류', '권익보호'] },
];
const JOB_OPTIONS = ['재직자', '자영업자', '미취업자', '프리랜서', '일용근로자', '(예비)창업자', '단기근로자', '영농종사자', '기타', '제한없음'];
const EDU_OPTIONS = ['고졸 미만', '고교 재학', '고졸 예정', '고교 졸업', '대학 재학', '대졸 예정', '대학 졸업', '석·박사', '기타', '제한없음'];
const REC_POLICIES: RecPolicy[] = [
  { id: 1, title: '청년 월세지원', tag: '주거', summary: '월 20만원, 최대 12개월 지원', reason: '현재 소득 구간과 직업군에 부합해요', impact: 'up', impactText: '이용 시 신용점수 상승 가능' },
  { id: 2, title: '소상공인 정책자금', tag: '경제', summary: '저금리 대출, 최대 5천만원', reason: '자영업 창업 준비 이력과 매칭돼요', impact: 'down', impactText: '연체 시 신용점수 하락 유의' },
  { id: 3, title: '청년 일자리 도약장려금', tag: '일자리', summary: '6개월 근속 시 장려금 지급', reason: '구직활동 이력과 연령 조건에 맞아요', impact: 'up', impactText: '이용 시 신용점수 상승 가능' },
];
const REC_SCORE = 72;
const REC_GRADE = '안정';

function Skeleton({ delay, style }: { delay: number; style?: object }) {
  const op = useState(() => new Animated.Value(0.5))[0];
  useEffect(() => {
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(op, { toValue: 1, duration: 700, delay, useNativeDriver: true }),
      Animated.timing(op, { toValue: 0.5, duration: 700, useNativeDriver: true }),
    ]));
    loop.start();
    return () => loop.stop();
  }, []);
  return <Animated.View style={[styles.skeleton, style, { opacity: op }]} />;
}

function AiRecommendationLoading({ progress }: { progress: RecommendationProgress }) {
  const message = progress.message || 'AI 추천을 준비하고 있어요';
  const policyLabel = progress.stage === 'REPORT_GENERATING' ? '리포트를 정리하고 있어요' : '맞춤 정책을 고르고 있어요';
  return <View style={styles.aiLoadingWrap}>
    <View style={styles.aiLoadingStatus}><View style={styles.aiLoadingDot} /><View><Text style={styles.aiLoadingTitle}>AI 추천 결과 생성 중</Text><Text style={styles.aiLoadingCopy}>{message}</Text></View></View>
    <View style={styles.aiLoadingScoreCard}>
      <Text style={styles.aiLoadingLabel}>경제 안정성 점수</Text>
      <View style={styles.aiLoadingScoreRow}><Skeleton delay={0} style={styles.aiLoadingCircle} /><View style={styles.aiLoadingScoreLines}><Skeleton delay={100} style={styles.aiLoadingLineLong} /><Skeleton delay={180} style={styles.aiLoadingLineShort} /></View></View>
    </View>
    <View style={styles.aiLoadingSectionHead}><Text style={styles.aiLoadingSectionTitle}>{policyLabel}</Text><Skeleton delay={250} style={styles.aiLoadingTinyLine} /></View>
    {[0, 1, 2].map((index) => <View key={index} style={styles.aiLoadingPolicyCard}><Skeleton delay={320 + index * 120} style={styles.aiLoadingTag} /><Skeleton delay={400 + index * 120} style={styles.aiLoadingPolicyTitle} /><Skeleton delay={480 + index * 120} style={styles.aiLoadingPolicyCopy} /><Skeleton delay={560 + index * 120} style={styles.aiLoadingReason} /></View>)}
  </View>;
}

function IntroReveal({ delay, style, children }: { delay: number; style?: any; children: React.ReactNode }) {
  const v = useState(() => new Animated.Value(0))[0];
  useEffect(() => {
    Animated.timing(v, { toValue: 1, duration: 420, delay, useNativeDriver: true }).start();
  }, []);
  return <Animated.View style={[style, { opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [10, 0] }) }] }]}>{children}</Animated.View>;
}

function RecIntro({ onDone, loggedIn, onLogin }: { onDone: () => void; loggedIn: boolean; onLogin: () => void }) {
  useEffect(() => {
    if (!loggedIn) return;
    const t = setTimeout(onDone, 2000);
    return () => clearTimeout(t);
  }, [loggedIn]);
  return (
    <Pressable disabled={!loggedIn} onPress={loggedIn ? onDone : undefined} style={styles.introPage}>
      <IntroReveal delay={80}><MaterialCommunityIcons name="star-four-points" size={40} color={theme.accent} /></IntroReveal>
      <IntroReveal delay={380} style={styles.introLineWrap}><Text style={styles.introTitle}>AI가 당신에게 딱 맞는</Text></IntroReveal>
      <IntroReveal delay={720} style={styles.introLineWrap}><Text style={styles.introTitle}>최적의 정책을 추천해드려요</Text></IntroReveal>
      {!loggedIn && (
        <IntroReveal delay={1050} style={styles.introGate}>
          <Text style={styles.introGateSub}>로그인 후 이용할 수 있어요</Text>
          <Pressable style={styles.introLoginBtn} onPress={onLogin}>
            <Text style={styles.introLoginText}>로그인하러 가기</Text>
          </Pressable>
        </IntroReveal>
      )}
    </Pressable>
  );
}

function Recommendation({ onSave, loggedIn, goLogin }: { onSave: (r: SavedRec) => void; loggedIn: boolean; goLogin: () => void }) {
  const [step, setStep] = useState<RecStep>('INTRO');
  const [justSaved, setJustSaved] = useState(false);
  const [majorKey, setMajorKey] = useState('job');
  const [selectedSubs, setSelectedSubs] = useState<string[]>([]);
  const [kcbConnection, setKcbConnection] = useState<KcbConnection | null>(null);
  const [kcbLinking, setKcbLinking] = useState(false);
  const [jobGroup, setJobGroup] = useState('재직자');
  const [education, setEducation] = useState('대학 졸업');
  const [editingField, setEditingField] = useState<'job' | 'edu' | null>(null);
  const [recommendationProgress, setRecommendationProgress] = useState<RecommendationProgress>({ stage: 'IDLE', message: 'AI 추천을 준비하고 있어요', percent: 0, completed: false });
  const [saved, setSaved] = useState<Record<number, boolean>>({});
  const [recommendationsExpanded, setRecommendationsExpanded] = useState(false);
  const [result, setResult] = useState<DiagnoseResult | null>(null);
  const [recError, setRecError] = useState<string | null>(null);
  const [exportingPdf, setExportingPdf] = useState(false);

  const linkKcb = async () => {
    if (kcbLinking) return;
    setKcbLinking(true);
    try {
      // 백엔드에 KCB 연동 정보를 저장한다: POST /api/v1/kcb/connect
      const res = await connectKcb();
      const day = new Date(res.createdAt);
      setKcbConnection({
        score: res.creditScore,
        grade: res.creditGrade,
        updatedAt: (isNaN(day.getTime()) ? new Date() : day).toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' }),
      });
    } catch (e: any) {
      Alert.alert('연동 실패', e?.message ?? 'KCB 연동에 실패했어요. 다시 시도해주세요.');
    } finally {
      setKcbLinking(false);
    }
  };

  const currentMajor = MAJORS.find((m) => m.key === majorKey) ?? MAJORS[0];

  const reset = () => { setStep('CAT'); setMajorKey('job'); setSelectedSubs([]); setKcbConnection(null); setKcbLinking(false); setJobGroup('재직자'); setEducation('대학 졸업'); setEditingField(null); setRecommendationProgress({ stage: 'IDLE', message: 'AI 추천을 준비하고 있어요', percent: 0, completed: false }); setSaved({}); setRecommendationsExpanded(false); setResult(null); setRecError(null); setExportingPdf(false); };
  const toggleSub = (label: string) => setSelectedSubs((prev) => prev.includes(label) ? prev.filter((x) => x !== label) : [...prev, label]);

  useEffect(() => {
    if (step !== 'B') return;
    setRecommendationProgress({ stage: 'SCORING', message: 'AI가 경제 안정성 점수를 판단하고 있어요', percent: 20, completed: false });
    setRecError(null);
    let alive = true;
    const started = Date.now();
    const pollProgress = () => { void getRecommendationProgress().then((progress) => { if (alive && progress.stage !== 'IDLE') setRecommendationProgress(progress); }).catch(() => {}); };
    pollProgress();
    const progressTimer = setInterval(pollProgress, 600);
    // 실제 백엔드 호출: 서버가 연동 저장된 KCB로 점수 산정 + 정책 추천
    requestDiagnose()
      .then((res) => { if (alive) { setResult(res); setRecommendationsExpanded(false); } })
      .catch((e) => { if (alive) { setResult(null); setRecError(e?.message ?? '추천을 불러오지 못했어요'); } })
      .finally(() => {
        if (!alive) return;
        // 최소 로딩 연출 유지(1.8초) 후 결과로 전환
        const wait = Math.max(0, 1800 - (Date.now() - started));
        setTimeout(() => { if (alive) setStep('C'); }, wait);
      });
    return () => { alive = false; clearInterval(progressTimer); };
  }, [step]);

  const recScore = result?.creditScore ?? REC_SCORE;
  const recGrade = result?.typeLabel ?? REC_GRADE;
  const recIsVulnerable = result?.userType === 'VULNERABLE';
  const recCards = result
    ? result.recommendations.map((p) => ({ id: p.policyId, tag: p.lclsfNm ?? '정책', title: p.plcyNm, summary: p.benefit ?? '', reason: p.reason ?? '', caution: p.caution ?? '' }))
    : REC_POLICIES.map((p) => ({ id: p.id, tag: p.tag, title: p.title, summary: p.summary, reason: p.reason, caution: '' }));
  // 첫 정책만 기본 노출하고, 나머지 4개(또는 잔여 정책)는 사용자가 펼쳐서 확인한다.
  const visibleRecCards = recommendationsExpanded ? recCards : recCards.slice(0, 1);

  const downloadPdf = async () => {
    if (exportingPdf) return;
    setExportingPdf(true);
    try {
      const html = recommendationReportHtml(recScore, recGrade, recCards, result?.aiReport ?? null);
      await downloadRecommendationPdf(html);
    } catch (e: any) {
      Alert.alert('다운로드 실패', e?.message ?? 'PDF를 만들지 못했어요. 다시 시도해주세요.');
    } finally {
      setExportingPdf(false);
    }
  };

  if (step === 'INTRO') return <RecIntro onDone={() => setStep('CAT')} loggedIn={loggedIn} onLogin={goLogin} />;

  if (step === 'CAT') {
    return (
      <ScrollView contentContainerStyle={styles.recPage} showsVerticalScrollIndicator={false}>
        <Text style={styles.recKicker}>정책추천</Text>
        <Text style={styles.recTitle}>관심있는 정책 분야를{`\n`}선택해주세요</Text>
        <Text style={styles.recSub}>대분류 1개, 세부분야는 여러 개 선택할 수 있어요</Text>

        <Text style={styles.recLabel}>대분류</Text>
        <View style={styles.chipWrap}>
          {MAJORS.map((m) => (
            <Pressable key={m.key} onPress={() => { setMajorKey(m.key); setSelectedSubs([]); }} style={[styles.selChip, majorKey === m.key && styles.selChipOn]}>
              <Text style={[styles.selChipText, majorKey === m.key && styles.selChipTextOn]}>{m.label}</Text>
            </Pressable>
          ))}
        </View>

        <Text style={[styles.recLabel, { marginTop: 20 }]}>중분류 · {currentMajor.label} (복수 선택 가능)</Text>
        <View style={styles.chipWrap}>
          {currentMajor.subs.map((sub) => {
            const on = selectedSubs.includes(sub);
            return (
              <Pressable key={sub} onPress={() => toggleSub(sub)} style={[styles.subChip, on && styles.subChipOn]}>
                {on && <Feather name="check" size={13} color={theme.accent} />}
                <Text style={[styles.subChipText, on && styles.subChipTextOn]}>{sub}</Text>
              </Pressable>
            );
          })}
        </View>

        <Pressable disabled={selectedSubs.length === 0} onPress={() => setStep('A')} style={[styles.recBtn, selectedSubs.length === 0 ? styles.recBtnOff : styles.recBtnOn]}>
          <Text style={selectedSubs.length === 0 ? styles.recBtnTextOff : styles.recBtnTextOn}>다음</Text>
        </Pressable>
      </ScrollView>
    );
  }

  if (step === 'A') {
    return (
      <ScrollView contentContainerStyle={styles.recPage} showsVerticalScrollIndicator={false}>
        <Pressable onPress={() => setStep('CAT')} style={styles.recHeadRow} hitSlop={8}>
          <Feather name="chevron-left" size={18} color={theme.text} />
          <Text style={styles.recKicker}>정책추천</Text>
        </Pressable>
        <Text style={styles.recTitle}>정책추천을 위해{`\n`}정보를 확인해주세요</Text>

        <View style={styles.creditBox}>
          {!kcbConnection ? (
            <>
              <Text style={styles.creditTitle}>신용정보 연동</Text>
              <Text style={styles.recSub}>KCB 신용정보를 안전하게 불러와요</Text>
              <Pressable disabled={kcbLinking} onPress={linkKcb} style={[styles.creditBtn, kcbLinking && styles.creditBtnDisabled]} accessibilityRole="button">
                <Text style={styles.creditBtnText}>{kcbLinking ? 'KCB 정보 불러오는 중…' : 'KCB 신용정보 연동하기'}</Text>
              </Pressable>
            </>
          ) : (
            <>
              <View style={styles.creditLinkedRow}>
                <View style={styles.linkedBadge}><Text style={styles.linkedBadgeText}>연동됨</Text></View>
                <Text style={styles.recSub}>KCB 신용점수 {kcbConnection.score}점 · {kcbConnection.grade}</Text>
              </View>
              <Text style={styles.creditUpdated}>기준일 {kcbConnection.updatedAt}</Text>
              <Pressable disabled={kcbLinking} onPress={linkKcb} style={styles.creditOutlineBtn} accessibilityRole="button">
                <Text style={styles.creditOutlineText}>{kcbLinking ? '갱신 중…' : '최신 정보로 불러오기'}</Text>
              </Pressable>
            </>
          )}
        </View>

        <EditField label="직업군" value={jobGroup} editing={editingField === 'job'} options={JOB_OPTIONS} onToggle={() => setEditingField((f) => (f === 'job' ? null : 'job'))} onPick={(v) => { setJobGroup(v); setEditingField(null); }} />
        <EditField label="학력" value={education} editing={editingField === 'edu'} options={EDU_OPTIONS} onToggle={() => setEditingField((f) => (f === 'edu' ? null : 'edu'))} onPick={(v) => { setEducation(v); setEditingField(null); }} />

        <Pressable disabled={!kcbConnection} onPress={() => setStep('B')} style={[styles.recBtn, { marginTop: 24 }, kcbConnection ? styles.recBtnOn : styles.recBtnOff]}>
          <Text style={kcbConnection ? styles.recBtnTextOn : styles.recBtnTextOff}>진단하기</Text>
        </Pressable>
      </ScrollView>
    );
  }

  if (step === 'B') {
    return (
      <View style={styles.recPage}>
        <AiRecommendationLoading progress={recommendationProgress} />
      </View>
    );
  }

  return (
    <View style={styles.flex}>
      <ScrollView contentContainerStyle={styles.recPage} showsVerticalScrollIndicator={false}>
        <View style={styles.recHeadRow}>
          <Pressable onPress={() => setStep('A')} hitSlop={8}>
            <Feather name="chevron-left" size={18} color={theme.text} />
          </Pressable>
          <Text style={styles.recKicker}>추천 결과</Text>
          <Pressable onPress={reset} style={{ marginLeft: 'auto' }} hitSlop={8}><Text style={styles.recReset}>처음부터 다시</Text></Pressable>
        </View>

        {recError && <Text style={[styles.recSub, { color: theme.accent, marginBottom: 8 }]}>추천 서버 응답 실패 — 예시 결과를 표시합니다 ({recError})</Text>}

        <View style={styles.gaugeBox}>
          <Text style={styles.scoreBoxTitle}>경제 안정성 점수</Text>
          <View style={styles.scoreBoxContent}>
            <ScoreGauge score={recScore} vulnerable={recIsVulnerable} />
            <View>
              <Text style={styles.recSub}>AI 경제 유형</Text>
            <Text style={[styles.gaugeGrade, { color: stabilityColor(recIsVulnerable) }]}>{recGrade}</Text>
            </View>
          </View>
        </View>

        <View style={styles.recommendationSection}>
          <View style={styles.recommendationSectionHead}>
            <Text style={styles.recommendationSectionTitle}>추천 정책 {recCards.length}개</Text>
            <Text style={styles.recommendationSectionSub}>내 상황에 맞는 정책이에요</Text>
          </View>
          {visibleRecCards.map((p) => {
          const isSaved = !!saved[p.id];
          return <View key={p.id} style={styles.recCard}>
            <Pressable onPress={() => setSaved((s) => ({ ...s, [p.id]: !s[p.id] }))} style={styles.bookmark} hitSlop={8} accessibilityRole="button" accessibilityLabel={`${p.title} 저장`}>
              <MaterialCommunityIcons name={isSaved ? 'bookmark' : 'bookmark-outline'} size={20} color={isSaved ? theme.accent : '#8C9CA6'} />
            </Pressable>
            <View style={styles.tag}><Text style={styles.tagText}>{p.tag}</Text></View>
            <Text style={styles.recCardTitle}>{p.title}</Text>
            <Text numberOfLines={2} ellipsizeMode="tail" style={styles.recCardSummary}>{p.summary}</Text>
            <View style={styles.reasonBox}><Text style={styles.reasonText}>추천 이유 · {p.reason}</Text></View>
            {!!p.caution && <Text numberOfLines={2} ellipsizeMode="tail" style={styles.recCardCaution}>신청 전 확인 · {p.caution}</Text>}
          </View>;
          })}
          {recCards.length > 1 && <Pressable onPress={() => setRecommendationsExpanded((expanded) => !expanded)} style={styles.recommendationToggle} accessibilityRole="button" accessibilityLabel={recommendationsExpanded ? '추천 정책 목록 접기' : '추천 정책 전체 보기'}>
            <Text style={styles.recommendationToggleText}>{recommendationsExpanded ? '추천 정책 접기' : `나머지 ${recCards.length - 1}개 정책 보기`}</Text>
            <Feather name={recommendationsExpanded ? 'chevron-up' : 'chevron-down'} size={18} color={theme.accent} />
          </Pressable>}
        </View>

        {result?.aiReport && <View style={styles.aiReportSection}><Text style={styles.aiReportSectionTitle}>AI 리포트</Text><Text style={styles.aiReportSectionSub}>경제 데이터 기반 분석 결과예요</Text><EconomicInsights report={result.aiReport} /></View>}
        <View style={styles.saveBarInline}>
        <View style={styles.resultActionRow}>
          <Pressable disabled={exportingPdf} onPress={() => { void downloadPdf(); }} style={[styles.downloadBtn, exportingPdf && styles.actionDisabled]}>
            <Feather name="download" size={14} color={theme.accent} />
            <Text style={styles.downloadBtnText}>{exportingPdf ? '생성 중' : '다운로드'}</Text>
          </Pressable>
          <Pressable
            disabled={justSaved}
            onPress={() => {
              void saveRecommendationResult().then(() => {
              onSave({ score: recScore, grade: recGrade, policyIds: recCards.map((p) => p.id) });
              setJustSaved(true);
              Alert.alert('저장 완료', '마이 › 저장한 정책 추천에서 다시 볼 수 있어요.');
            }).catch((e) => Alert.alert('저장 실패', e?.message ?? '추천 정책을 저장하지 못했어요.'));
            }}
            style={[styles.saveBtn, styles.saveBtnGrow, justSaved && styles.saveBtnDone]}
          >
            <Feather name={justSaved ? 'check' : 'bookmark'} size={16} color="#fff" />
            <Text style={styles.saveBtnText}>{justSaved ? '저장됨' : '이 추천 결과 저장하기'}</Text>
          </Pressable>
          {!justSaved && <Pressable onPress={() => Alert.alert('추천 결과 저장 안내', '이 화면을 닫거나 새 진단을 시작하면 현재 추천 결과는 사라질 수 있어요. 나중에 다시 보고 싶다면 저장하기를 눌러주세요.')} style={styles.saveInfoButton} hitSlop={8} accessibilityRole="button" accessibilityLabel="추천 결과 저장 안내">
            <Feather name="help-circle" size={18} color={theme.accent} />
          </Pressable>}
        </View>
        </View>
      </ScrollView>
    </View>
  );
}

type RecommendationReportCard = { tag: string; title: string; summary: string; reason: string; caution: string };

async function downloadRecommendationPdf(html: string): Promise<void> {
  if (Platform.OS === 'web') {
    await Print.printAsync({ html });
    Alert.alert('PDF 저장', '인쇄 창에서 “PDF로 저장”을 선택해주세요.');
    return;
  }

  const file = await Print.printToFileAsync({ html, base64: false });
  if (Platform.OS === 'android') {
    // Android의 scoped storage에서는 사용자가 저장할 폴더를 선택해야 앱이 실제 파일을 쓸 수 있다.
    const permission = await FileSystem.StorageAccessFramework.requestDirectoryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert('저장 취소', 'PDF를 저장할 폴더를 선택하지 않았어요.');
      return;
    }

    const fileName = `DIVE_정책추천_${new Date().toISOString().slice(0, 10)}.pdf`;
    const destinationUri = await FileSystem.StorageAccessFramework.createFileAsync(
      permission.directoryUri,
      fileName,
      'application/pdf',
    );
    const base64 = await FileSystem.readAsStringAsync(file.uri, { encoding: FileSystem.EncodingType.Base64 });
    await FileSystem.writeAsStringAsync(destinationUri, base64, { encoding: FileSystem.EncodingType.Base64 });
    Alert.alert('PDF 저장 완료', '선택한 폴더에 PDF를 저장했어요.');
    return;
  }

  // iOS는 사용자가 파일 앱 등의 저장 위치를 선택하도록 시스템 공유 시트를 사용한다.
  if (await Sharing.isAvailableAsync()) {
    await Sharing.shareAsync(file.uri, { mimeType: 'application/pdf', UTI: '.pdf' });
    return;
  }
  Alert.alert('PDF 생성 완료', `파일 경로: ${file.uri}`);
}

function recommendationReportHtml(score: number, typeLabel: string, cards: RecommendationReportCard[], aiReport: DiagnoseResult['aiReport']) {
  const escape = (value: string) => value.replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char] ?? char));
  const policies = cards.map((item, index) => `<section class="policy"><p class="tag">${escape(item.tag || '정책')}</p><h3>${index + 1}. ${escape(item.title)}</h3><p>${escape(item.summary || '지원 내용을 확인해주세요.')}</p><p class="reason">추천 이유 · ${escape(item.reason || '내 상황에 맞는 정책입니다.')}</p>${item.caution ? `<p class="caution">신청 전 확인 · ${escape(item.caution)}</p>` : ''}</section>`).join('');
  const feedback = aiReport?.feedback.map((item) => `<li><strong>${escape(item.category)}</strong> · ${escape(item.message)}${item.evidence ? `<br><span class="evidence">근거: ${escape(item.evidence)}</span>` : ''}</li>`).join('') ?? '';
  const comparisons = aiReport?.peerComparisons.map((item) => `<li>${escape(item.metric)}: 평균 대비 ${item.gapPercent == null ? '-' : `${item.gapPercent > 0 ? '+' : ''}${item.gapPercent.toFixed(1)}%`} (${escape(item.direction)})</li>`).join('') ?? '';
  const guides = aiReport?.guides.map((item, index) => `<li><strong>${escape(`${item.priority ?? index + 1}. ${item.title}`)}</strong> — ${escape(item.action)}</li>`).join('') ?? '';
  const housing = aiReport?.housingBenchmark;
  const aiSection = aiReport ? `<section class="report"><h2>AI 리포트</h2><h3>${escape(aiReport.economicTypeName || typeLabel)}</h3>${aiReport.summary ? `<p>${escape(aiReport.summary)}</p>` : ''}<p class="meta">분석 신뢰도 ${aiReport.typeConfidence == null ? '확인 중' : `${Math.round(aiReport.typeConfidence * 100)}%`}</p>${feedback ? `<h3>항목별 분석</h3><ul>${feedback}</ul>` : ''}${comparisons ? `<h3>또래 평균 비교</h3><ul>${comparisons}</ul>` : ''}${housing ? `<h3>${escape(housing.region)} 주거 참고</h3><p>월세 중앙값 ${housing.monthlyRentMedian ?? '-'}만원 · 전세보증금 중앙값 ${housing.jeonseDepositMedian ?? '-'}만원</p>` : ''}${guides ? `<h3>지금 해볼 일</h3><ul>${guides}</ul>` : ''}${aiReport.disclaimer ? `<p class="foot">${escape(aiReport.disclaimer)}</p>` : ''}</section>` : '';
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>body{font-family:Arial,'Malgun Gothic',sans-serif;color:#173B57;padding:28px;line-height:1.55}.head{border-bottom:3px solid #3B9FD8;padding-bottom:16px}.score{font-size:40px;font-weight:800;color:#1689C5}.tag{color:#1689C5;font-size:12px;font-weight:700;margin:0}.policy,.report{border:1px solid #DCE7EC;border-radius:12px;padding:15px;margin:12px 0}.policy h3,.report h3{margin:8px 0}.policy p,.report p{margin:5px 0;color:#4F6675}.report ul{padding-left:20px;color:#4F6675}.report li{margin:7px 0}.reason{background:#EFF8FD;padding:8px;border-radius:7px}.caution,.evidence,.meta{font-size:12px;color:#748995}.foot{margin-top:24px;color:#748995;font-size:11px}</style></head><body><div class="head"><h1>DIVE 정책 추천 결과</h1><div class="score">${Math.round(score)} / 100</div><p>${escape(typeLabel)} · ${new Date().toLocaleDateString('ko-KR')}</p></div><h2>추천 정책 ${cards.length}개</h2>${policies}${aiSection}<p class="foot">정책별 신청 자격·기간·제출 서류는 신청 전 반드시 원문 공고에서 확인해주세요.</p></body></html>`;
}

function stabilityColor(vulnerable: boolean) { return vulnerable ? '#D9485F' : theme.accent; }

function ScoreGauge({ score, vulnerable = false }: { score: number; vulnerable?: boolean }) {
  const segments = 72;
  const filled = Math.round((Math.max(0, Math.min(100, score)) / 100) * segments);
  return <View style={styles.gaugeRing} accessibilityLabel={`안정성 점수 ${Math.round(score)}점`}>{Array.from({ length: segments }, (_, index) => (
    <View key={index} style={[styles.gaugeSegment, { transform: [{ rotate: `${index * (360 / segments)}deg` }, { translateY: -34 }] }, index < filled ? { backgroundColor: stabilityColor(vulnerable) } : styles.gaugeSegmentOff]} />
  ))}<View style={styles.gaugeInner}><Text style={styles.gaugeScore}>{Math.round(score)}</Text><Text style={styles.gaugeUnit}>/ 100</Text></View></View>;
}

function EditField({ label, value, editing, options, onToggle, onPick }: { label: string; value: string; editing: boolean; options: string[]; onToggle: () => void; onPick: (v: string) => void }) {
  return (
    <View style={styles.editField}>
      <View style={styles.editFieldHead}>
        <Text style={styles.recSub}>{label}</Text>
        <Pressable onPress={onToggle} hitSlop={8}><Feather name="edit-2" size={14} color={theme.textMuted} /></Pressable>
      </View>
      {!editing ? (
        <Text style={styles.editFieldValue}>{value}</Text>
      ) : (
        <View style={[styles.chipWrap, { marginTop: 8 }]}>
          {options.map((o) => (
            <Pressable key={o} onPress={() => onPick(o)} style={[styles.subChip, o === value && styles.subChipOn]}>
              <Text style={[styles.subChipText, o === value && styles.subChipTextOn]}>{o}</Text>
            </Pressable>
          ))}
        </View>
      )}
    </View>
  );
}

function EconomicInsights({ report }: { report: NonNullable<DiagnoseResult['aiReport']> }) {
  const [expanded, setExpanded] = useState(false);
  const confidence = report.typeConfidence == null ? null : Math.round(report.typeConfidence * 100);
  const vulnerable = report.majorClass === '취약' || ['E4', 'E5', 'E6'].includes(report.economicType);
  const color = stabilityColor(vulnerable);
  return <View style={styles.insightCard}>
    <View style={styles.insightHead}><View><Text style={[styles.insightTitle, { color }]}>{report.economicTypeName || '경제 분석'}</Text>{expanded && <Text style={[styles.insightMeta, { color }]}>{report.economicType} · {report.majorClass}</Text>}</View><Pressable onPress={() => setExpanded((value) => !value)} style={styles.insightToggle} accessibilityRole="button" accessibilityLabel={expanded ? 'AI 리포트 접기' : 'AI 리포트 전체 보기'}><Text style={styles.insightToggleText}>{expanded ? '접기' : '전체보기'}</Text><Feather name={expanded ? 'chevron-up' : 'chevron-down'} size={16} color={color} /></Pressable></View>
    {expanded && <>
      {!!report.summary && <Text style={styles.insightSummary}>{report.summary}</Text>}
      <View style={styles.insightRow}><Text style={styles.insightLabel}>분석 신뢰도</Text><Text style={styles.insightValue}>{confidence == null ? '확인 중' : `${confidence}%`}</Text></View>
      {report.feedback.map((item, index) => <View key={`${item.category}-${index}`} style={styles.insightItem}><Text style={styles.insightItemTitle}>{item.category}</Text><Text style={styles.insightItemText}>{item.message}</Text>{!!item.evidence && <Text style={styles.insightEvidence}>{item.evidence}</Text>}</View>)}
      {report.peerComparisons.length > 0 && <View style={styles.insightItem}><Text style={styles.insightItemTitle}>또래 평균 비교</Text>{report.peerComparisons.map((item, index) => <Text key={`${item.metric}-${index}`} style={styles.insightItemText}>{`${item.metric}: 평균 대비 ${item.gapPercent == null ? '-' : `${item.gapPercent > 0 ? '+' : ''}${item.gapPercent.toFixed(1)}%`} (${item.direction})`}</Text>)}</View>}
      {report.housingBenchmark && <View style={styles.insightItem}><Text style={styles.insightItemTitle}>{report.housingBenchmark.region} 주거 참고</Text><Text style={styles.insightItemText}>월세 중앙값 {report.housingBenchmark.monthlyRentMedian ?? '-'}만원 · 전세보증금 중앙값 {report.housingBenchmark.jeonseDepositMedian ?? '-'}만원</Text></View>}
      {report.guides.length > 0 && <View style={styles.insightItem}><Text style={styles.insightItemTitle}>지금 해볼 일</Text>{report.guides.map((guide, index) => <Text key={`${guide.title}-${index}`} style={styles.insightItemText}>{`${guide.priority ?? index + 1}. ${guide.title} — ${guide.action}`}</Text>)}</View>}
      {!!report.disclaimer && <Text style={styles.insightFoot}>{report.disclaimer}</Text>}
    </>}
  </View>;
}

function GongguList({ items, open, likedGonggu, onToggleGonggu, loggedIn, goLogin, onCreated }: {
  items: Gonggu[];
  open: (g: Gonggu) => void;
  likedGonggu: Record<string, boolean>;
  onToggleGonggu: (id: string) => void;
  loggedIn: boolean;
  goLogin: () => void;
  onCreated: () => Promise<void>;
}) {
  const [formOpen, setFormOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [productUrl, setProductUrl] = useState('');
  const [price, setPrice] = useState('');
  const [targetCount, setTargetCount] = useState('');
  const [imageAsset, setImageAsset] = useState<ImagePicker.ImagePickerAsset | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const openCreateForm = () => {
    if (!loggedIn) {
      goLogin();
      return;
    }
    setFormOpen(true);
  };

  const register = async () => {
    const amount = Number(price.replace(/,/g, ''));
    const count = Number(targetCount);
    if (!title.trim() || !Number.isInteger(amount) || amount <= 0 || !Number.isInteger(count) || count <= 0) {
      Alert.alert('입력 확인', '제목, 참여 금액, 목표 인원을 올바르게 입력해주세요.');
      return;
    }
    if (productUrl.trim() && !/^https?:\/\//i.test(productUrl.trim())) {
      Alert.alert('링크 확인', '상품 링크는 http:// 또는 https://로 시작해야 해요.');
      return;
    }
    const now = new Date();
    const end = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
    const localDateTime = (date: Date) => date.toISOString().slice(0, 19);
    setSubmitting(true);
    try {
      await createGonggu({ title: title.trim(), content: content.trim(), price: amount, targetCount: count, startDate: localDateTime(now), endDate: localDateTime(end), productUrl: productUrl.trim() || undefined, productImage: imageAsset ? { uri: imageAsset.uri, mimeType: imageAsset.mimeType } : undefined });
      setFormOpen(false);
      setTitle(''); setContent(''); setProductUrl(''); setPrice(''); setTargetCount(''); setImageAsset(null);
      await onCreated();
      Alert.alert('등록 완료', '공동구매가 등록되었습니다. 모집 기간은 7일입니다.');
    } catch (e) {
      Alert.alert('등록 실패', e instanceof Error ? e.message : '공동구매를 등록하지 못했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  const confirmSubmit = () => {
    const amount = Number(price.replace(/,/g, ''));
    const count = Number(targetCount);
    if (!title.trim() || !Number.isInteger(amount) || amount <= 0 || !Number.isInteger(count) || count <= 0) {
      Alert.alert('입력 확인', '제목, 참여 금액, 목표 인원을 올바르게 입력해주세요.');
      return;
    }
    Alert.alert(
      '공동구매를 등록할까요?',
      '등록 후에는 내용을 수정하거나 삭제할 수 없습니다. 입력한 내용을 다시 확인해주세요.',
      [
        { text: '취소', style: 'cancel' },
        { text: '등록하기', style: 'destructive', onPress: () => { void register(); } },
      ],
    );
  };

  const pickImage = async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert('사진 권한 필요', '공구 이미지를 등록하려면 사진 접근 권한을 허용해주세요.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: true, aspect: [1, 1], quality: 0.8 });
    if (!result.canceled) setImageAsset(result.assets[0]);
  };

  return <View style={styles.flex}>
    <View style={styles.screenHeader}>
      <View style={styles.gongguListHead}><View><Text style={styles.screenTitle}>공동구매</Text><Text style={styles.subtitle}>함께 모여 더 좋은 가격으로</Text></View><Pressable onPress={openCreateForm} style={styles.gongguCreateButton} accessibilityRole="button"><Feather name="plus" size={18} color="#fff" /><Text style={styles.gongguCreateButtonText}>공구 추가</Text></Pressable></View>
    </View>
    <FlatList data={items} keyExtractor={(x) => x.id} contentContainerStyle={styles.list} renderItem={({ item }) => <GongguCard item={item} onPress={() => open(item)} wide liked={!!likedGonggu[item.id]} onToggleLike={onToggleGonggu} />} />
    <Modal transparent visible={formOpen} animationType="slide" onRequestClose={() => setFormOpen(false)}>
      <View style={styles.modalDim}><View style={styles.gongguCreateSheet}>
        <View style={styles.gongguCreateSheetHead}><Text style={styles.modalTitle}>공동구매 등록</Text><Pressable onPress={() => setFormOpen(false)} disabled={submitting} hitSlop={10}><Feather name="x" size={22} color={theme.text} /></Pressable></View>
        <ScrollView keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
          <Text style={styles.gongguFormLabel}>공구 제목</Text><TextInput value={title} onChangeText={setTitle} placeholder="예: 세제 공구 할 사람" placeholderTextColor={theme.textFaint} style={styles.gongguFormInput} maxLength={200} />
          <Text style={styles.gongguFormLabel}>상세 설명</Text><TextInput value={content} onChangeText={setContent} placeholder="공구 내용과 참여 조건을 알려주세요" placeholderTextColor={theme.textFaint} style={[styles.gongguFormInput, styles.gongguFormTextarea]} multiline textAlignVertical="top" />
          <Text style={styles.gongguFormLabel}>상품 링크 (선택)</Text><TextInput value={productUrl} onChangeText={setProductUrl} placeholder="https://상품-페이지-주소" placeholderTextColor={theme.textFaint} style={styles.gongguFormInput} keyboardType="url" autoCapitalize="none" autoCorrect={false} />
          <Text style={styles.gongguFormLabel}>상품 이미지 (선택)</Text>
          {imageAsset ? <View style={styles.gongguImagePreviewWrap}><Image source={{ uri: imageAsset.uri }} style={styles.gongguImagePreview} /><Pressable onPress={() => setImageAsset(null)} style={styles.gongguImageRemove} accessibilityLabel="선택한 상품 이미지 삭제"><Feather name="x" size={16} color="#fff" /></Pressable><Pressable onPress={pickImage} style={styles.gongguImageChange}><Text style={styles.gongguImageChangeText}>상품 사진 변경</Text></Pressable></View> : <Pressable onPress={pickImage} style={styles.gongguImagePicker} accessibilityRole="button"><Feather name="image" size={20} color={theme.accent} /><Text style={styles.gongguImagePickerText}>상품 사진 선택하기</Text></Pressable>}
          <Text style={styles.gongguFormLabel}>1인 참여 금액</Text><TextInput value={price} onChangeText={setPrice} placeholder="예: 10000" placeholderTextColor={theme.textFaint} style={styles.gongguFormInput} keyboardType="number-pad" />
          <Text style={styles.gongguFormLabel}>목표 인원</Text><TextInput value={targetCount} onChangeText={setTargetCount} placeholder="예: 5" placeholderTextColor={theme.textFaint} style={styles.gongguFormInput} keyboardType="number-pad" />
          <Text style={styles.gongguFormHint}>이미지는 선택 사항이며, 모집 기간은 등록일부터 7일입니다.</Text>
          <Primary label={submitting ? '등록 중…' : '공동구매 등록하기'} onPress={confirmSubmit} disabled={submitting} />
        </ScrollView>
      </View></View>
    </Modal>
  </View>;
}

type MySub = 'gonggu' | 'policy' | 'recommendations' | 'noti' | 'settings';

function MyPage({ member, loggingIn, onLogin, onLogout, onOnboard, onProfileUpdate, profileSaved, gonggus, openGonggu, openPolicy }: { member: Member | null; loggingIn: boolean; onLogin: () => void; onLogout: () => void; onOnboard: (career: string, finalEducation: string) => Promise<void>; onProfileUpdate: (nickname: string, career: string, finalEducation: string) => Promise<void>; profileSaved: boolean; gonggus: Gonggu[]; openGonggu: (g: Gonggu) => void; openPolicy: (p: Policy) => void }) {
  const [sub, setSub] = useState<MySub | null>(null);
  const [liked, setLiked] = useState<Policy[]>([]);
  const [profileEditorOpen, setProfileEditorOpen] = useState(false);
  const [nickname, setNickname] = useState('');
  const [career, setCareer] = useState('');
  const [education, setEducation] = useState('');
  const [savingProfile, setSavingProfile] = useState(false);
  useEffect(() => { if (member) getMyLikedPolicies().then(setLiked).catch(() => {}); }, [member]);
  if (!member) return <View style={styles.centerPage}><Text style={styles.heroTitle}>내 혜택을{`\n`}놓치지 마세요</Text><Text style={styles.centerCopy}>로그인하고 정책 추천과 참여 내역을 확인하세요.</Text><Primary label={loggingIn ? '로그인 중…' : '카카오로 시작하기'} onPress={onLogin} disabled={loggingIn} /></View>;
  if (!profileSaved) return <ProfileForm onOnboard={onOnboard} />;
  if (sub) return <MySubScreen sub={sub} onBack={() => setSub(null)} liked={liked} gonggus={gonggus} openGonggu={openGonggu} openPolicy={openPolicy} onLogout={onLogout} />;

  const name = member.nickname || (member.email ? member.email.split('@')[0] : '회원');
  const likedCount = liked.length;
  const menus: { id: MySub; label: string }[] = [
    { id: 'gonggu', label: '참여한 공동구매' },
    { id: 'policy', label: likedCount > 0 ? `관심 정책 (${likedCount})` : '관심 정책' },
    { id: 'recommendations', label: '저장한 정책 추천' },
    { id: 'noti', label: '알림 설정' },
    { id: 'settings', label: '서비스 설정' },
  ];
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text style={styles.screenTitle}>마이</Text>
      <View style={styles.profile}><Text style={styles.avatar}>{name.slice(0, 1).toUpperCase()}</Text><View style={{ flex: 1 }}><Text style={styles.profileName}>{name} 님</Text><Text style={styles.subtitle}>{member.career} · {member.finalEducation}</Text></View><Pressable onPress={() => { setNickname(name); setCareer(member.career); setEducation(member.finalEducation); setProfileEditorOpen(true); }} hitSlop={10} accessibilityRole="button" accessibilityLabel="프로필 수정"><Feather name="edit-2" size={17} color={theme.textMuted} /></Pressable></View>
      {menus.map((m) => <Pressable key={m.id} style={styles.menu} onPress={() => setSub(m.id)}><Text>{m.label}</Text><Feather name="chevron-right" size={18} color={theme.textMuted} /></Pressable>)}
      <Pressable onPress={onLogout}><Text style={styles.logout}>로그아웃</Text></Pressable>
      <Modal visible={profileEditorOpen} transparent animationType="slide" onRequestClose={() => setProfileEditorOpen(false)}>
        <View style={styles.modalDim}><View style={styles.modalCard}>
          <Text style={styles.modalTitle}>프로필 수정</Text>
          <Text style={styles.formLabel}>닉네임</Text><TextInput value={nickname} onChangeText={setNickname} style={styles.formInput} maxLength={50} placeholder="닉네임" />
          <Text style={styles.formLabel}>직군</Text><TextInput value={career} onChangeText={setCareer} style={styles.formInput} maxLength={100} placeholder="직군" />
          <Text style={styles.formLabel}>학력</Text><TextInput value={education} onChangeText={setEducation} style={styles.formInput} maxLength={100} placeholder="학력" />
          <Primary label={savingProfile ? '저장 중…' : '저장하기'} disabled={savingProfile || !nickname.trim() || !career.trim() || !education.trim()} onPress={() => { setSavingProfile(true); void onProfileUpdate(nickname.trim(), career.trim(), education.trim()).then(() => { setProfileEditorOpen(false); Alert.alert('수정 완료', '프로필 정보를 수정했어요.'); }).catch((e) => Alert.alert('수정 실패', e?.message ?? '프로필을 수정하지 못했어요.')).finally(() => setSavingProfile(false)); }} />
          <Pressable onPress={() => setProfileEditorOpen(false)}><Text style={styles.cancel}>취소</Text></Pressable>
        </View></View>
      </Modal>
    </ScrollView>
  );
}

function MySubScreen({ sub, onBack, liked, gonggus, openGonggu, openPolicy, onLogout }: { sub: MySub; onBack: () => void; liked: Policy[]; gonggus: Gonggu[]; openGonggu: (g: Gonggu) => void; openPolicy: (p: Policy) => void; onLogout: () => void }) {
  const [noti, setNoti] = useState({ gonggu: true, policy: true, marketing: false });
  const [savedRecommendations, setSavedRecommendations] = useState<SavedRecommendationResultSummary[]>([]);
  const [selectedSavedResult, setSelectedSavedResult] = useState<SavedRecommendationResultDetail | null>(null);
  const title = { gonggu: '참여한 공동구매', policy: '관심 정책', recommendations: '저장한 정책 추천', noti: '알림 설정', settings: '서비스 설정' }[sub];

  useEffect(() => {
    if (sub !== 'noti') return;
    getNotificationSettings().then(setNoti).catch(() => {});
  }, [sub]);
  useEffect(() => {
    if (sub === 'recommendations') getSavedRecommendationResults().then(setSavedRecommendations).catch(() => setSavedRecommendations([]));
  }, [sub]);

  if (sub === 'recommendations' && selectedSavedResult) return <SavedRecommendationResultView detail={selectedSavedResult} onBack={() => setSelectedSavedResult(null)} openPolicy={openPolicy} />;

  const setNotiPref = (key: 'gonggu' | 'policy' | 'marketing', value: boolean) => {
    setNoti((s) => ({ ...s, [key]: value })); // 낙관적 반영
    updateNotificationSettings({ [key]: value }).catch(() => {
      setNoti((s) => ({ ...s, [key]: !value })); // 실패 시 되돌림
      Alert.alert('저장 실패', '알림 설정을 저장하지 못했어요.');
    });
  };
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Back onPress={onBack} />
      <Text style={styles.screenTitle}>{title}</Text>

      {sub === 'gonggu' && (gonggus.length === 0
        ? <MyEmpty text="아직 참여한 공동구매가 없어요" />
        : <View style={{ gap: 12, marginTop: 6 }}>{gonggus.map((g) => <GongguCard key={g.id} item={g} onPress={() => openGonggu(g)} wide />)}</View>)}

      {sub === 'policy' && (liked.length === 0
        ? <MyEmpty text="관심(좋아요)한 정책이 없어요" />
        : <View style={{ marginTop: 6 }}>{liked.map((p) => (
            <Pressable key={p.id} style={styles.polItem} onPress={() => openPolicy(p)}>
              <View style={styles.tag}><Text style={styles.tagText}>{p.category}</Text></View>
              <Text style={styles.polItemTitle}>{p.title}</Text>
              <Text style={styles.polItemSummary}>{p.summary}</Text>
              <View style={styles.polItemBottom}>
                <Text style={styles.polDeadline}>{p.deadline}</Text>
                <Text style={styles.polItemMore}>자세히보기 ›</Text>
              </View>
            </Pressable>
          ))}</View>)}

      {sub === 'recommendations' && (savedRecommendations.length === 0
        ? <MyEmpty text="저장한 정책 추천이 없어요" />
        : <View style={{ marginTop: 6 }}>{savedRecommendations.map((item) => <Pressable key={item.id} style={styles.polItem} onPress={() => { getSavedRecommendationResult(item.id).then(setSelectedSavedResult).catch((e) => Alert.alert('조회 실패', e?.message ?? '저장한 추천 결과를 불러오지 못했어요.')); }}>
            <View style={styles.savedResultHeader}><View style={[styles.tag, item.userType === 'VULNERABLE' && styles.tagVulnerable]}><Text style={[styles.tagText, item.userType === 'VULNERABLE' && styles.tagTextVulnerable]}>{item.typeLabel}</Text></View><Text style={[styles.savedResultScore, { color: stabilityColor(item.userType === 'VULNERABLE') }]}>{item.creditScore}점</Text></View>
            <Text style={styles.polItemTitle}>{item.title}</Text>
            <Text style={styles.polItemSummary}>저장 당시의 점수, 경제 리포트와 추천 정책 전체를 다시 볼 수 있어요.</Text>
            <View style={styles.polItemBottom}><Text style={styles.polDeadline}>저장일 {item.savedAt.slice(0, 10)}</Text><Text style={styles.polItemMore}>결과 보기 ›</Text></View>
          </Pressable>)}</View>)}

      {sub === 'noti' && (
        <View style={{ marginTop: 6 }}>
          <NotiRow label="공구 참여·마감 알림" value={noti.gonggu} onChange={(v) => setNotiPref('gonggu', v)} />
          <NotiRow label="정책 마감 알림" value={noti.policy} onChange={(v) => setNotiPref('policy', v)} />
          <NotiRow label="마케팅 정보 수신" value={noti.marketing} onChange={(v) => setNotiPref('marketing', v)} />
        </View>
      )}

      {sub === 'settings' && (
        <View style={{ marginTop: 6 }}>
          <View style={styles.menu}><Text>버전 정보</Text><Text style={styles.subtitle}>1.0.0</Text></View>
          <Pressable style={styles.menu} onPress={() => Alert.alert('이용약관', '준비 중입니다.')}><Text>이용약관</Text><Feather name="chevron-right" size={18} color={theme.textMuted} /></Pressable>
          <Pressable style={styles.menu} onPress={() => Alert.alert('개인정보처리방침', '준비 중입니다.')}><Text>개인정보처리방침</Text><Feather name="chevron-right" size={18} color={theme.textMuted} /></Pressable>
          <Pressable style={styles.menu} onPress={onLogout}><Text style={{ color: theme.accent, fontWeight: '700' }}>로그아웃</Text><Feather name="chevron-right" size={18} color={theme.accent} /></Pressable>
        </View>
      )}
    </ScrollView>
  );
}

function NotiRow({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <View style={styles.menu}>
      <Text>{label}</Text>
      <Switch value={value} onValueChange={onChange} trackColor={{ true: theme.accent, false: '#D8E3E9' }} thumbColor="#fff" />
    </View>
  );
}

function MyEmpty({ text }: { text: string }) {
  return <View style={styles.polEmpty}><Text style={styles.polEmptyText}>{text}</Text></View>;
}

function recommendedPolicyToPolicy(item: DiagnoseResult['recommendations'][number]): Policy {
  return {
    id: String(item.policyId),
    title: item.plcyNm,
    category: item.lclsfNm || '정책',
    subCategory: '',
    summary: item.benefit,
    benefit: item.benefit,
    period: '신청 기간 확인 필요',
    deadline: '신청 기간 확인 필요',
    days: 9999,
    popularity: 0,
    description: item.benefit,
    institution: '주관기관 정보 확인 필요',
    targetAge: '연령 기준 확인 필요',
    applyUrl: '',
  };
}

function SavedRecommendationResultView({ detail, onBack, openPolicy }: { detail: SavedRecommendationResultDetail; onBack: () => void; openPolicy: (policy: Policy) => void }) {
  const { result } = detail;
  const [exportingPdf, setExportingPdf] = useState(false);
  const downloadPdf = async () => {
    if (exportingPdf) return;
    setExportingPdf(true);
    try {
      const cards = result.recommendations.map((item) => ({ tag: item.lclsfNm || '정책', title: item.plcyNm, summary: item.benefit || '', reason: item.reason || '', caution: item.caution || '' }));
      const html = recommendationReportHtml(result.creditScore, result.typeLabel, cards, result.aiReport);
      await downloadRecommendationPdf(html);
    } catch (e: any) {
      Alert.alert('다운로드 실패', e?.message ?? 'PDF를 만들지 못했어요. 다시 시도해주세요.');
    } finally {
      setExportingPdf(false);
    }
  };
  return <ScrollView contentContainerStyle={styles.page}>
    <Back onPress={onBack} />
    <Text style={styles.screenTitle}>{detail.title}</Text>
    <Text style={styles.subtitle}>저장일 {detail.savedAt.slice(0, 10)}</Text>
    <Pressable disabled={exportingPdf} onPress={() => { void downloadPdf(); }} style={[styles.savedReportDownload, exportingPdf && styles.actionDisabled]} accessibilityRole="button"><Feather name="download" size={15} color={theme.accent} /><Text style={styles.savedReportDownloadText}>{exportingPdf ? 'PDF 생성 중…' : 'PDF 다운로드'}</Text></Pressable>
    <View style={styles.gaugeBox}><Text style={styles.scoreBoxTitle}>경제 안정성 점수</Text><View style={styles.scoreBoxContent}><ScoreGauge score={result.creditScore} vulnerable={result.userType === 'VULNERABLE'} /><View><Text style={styles.recSub}>AI 경제 유형</Text><Text style={[styles.gaugeGrade, { color: stabilityColor(result.userType === 'VULNERABLE') }]}>{result.typeLabel}</Text></View></View></View>
    <Text style={styles.recommendationSectionTitle}>추천 정책 {result.recommendations.length}개</Text>
    <View style={{ marginTop: 12 }}>{result.recommendations.map((item) => <Pressable key={item.policyId} style={styles.polItem} onPress={() => openPolicy(recommendedPolicyToPolicy(item))}>
      <View style={styles.tag}><Text style={styles.tagText}>{item.lclsfNm || '정책'}</Text></View><Text style={styles.polItemTitle}>{item.plcyNm}</Text><Text numberOfLines={2} ellipsizeMode="tail" style={styles.polItemSummary}>{item.benefit}</Text><View style={styles.reasonBox}><Text style={styles.reasonText}>추천 이유 · {item.reason}</Text></View><Text style={styles.polItemMore}>자세히보기 ›</Text>
    </Pressable>)}</View>
    {result.aiReport && <View style={styles.aiReportSection}><Text style={styles.aiReportSectionTitle}>AI 리포트</Text><Text style={styles.aiReportSectionSub}>저장 당시의 경제 데이터 기반 분석 결과예요</Text><EconomicInsights report={result.aiReport} /></View>}
  </ScrollView>;
}

function ProfileForm({ onOnboard }: { onOnboard: (career: string, finalEducation: string) => Promise<void> }) {
  // jobCd(career) / schoolCd(finalEducation) — 온보딩 API로 전송
  const [job, setJob] = useState('');
  const [edu, setEdu] = useState('');
  const [saving, setSaving] = useState(false);
  const submit = async () => {
    if (saving || !job || !edu) return;
    setSaving(true);
    try { await onOnboard(job, edu); }
    catch (e) { Alert.alert('저장 실패', e instanceof Error ? e.message : '다시 시도해주세요.'); }
    finally { setSaving(false); }
  };
  return (
    <View style={styles.centerPage}>
      <Text style={styles.heroTitle}>마지막으로{`\n`}정보를 알려주세요</Text>
      <SelectField label="직군 / 취업요건" placeholder="직군을 선택해주세요" value={job} options={JOB_OPTIONS} onSelect={setJob} />
      <SelectField label="학력" placeholder="학력을 선택해주세요" value={edu} options={EDU_OPTIONS} onSelect={setEdu} />
      <Primary label={saving ? '저장 중…' : '저장하고 시작하기'} onPress={submit} disabled={!job || !edu || saving} />
    </View>
  );
}

function SelectField({ label, value, placeholder, options, onSelect }: { label: string; value: string; placeholder: string; options: string[]; onSelect: (v: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <View style={styles.selectWrap}>
      <Pressable style={styles.select} onPress={() => setOpen(true)}>
        <Text style={value ? styles.selectValue : styles.selectPlaceholder}>{value || placeholder}</Text>
        <Feather name="chevron-down" size={18} color={theme.textMuted} />
      </Pressable>
      <Modal transparent visible={open} animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.selectDim} onPress={() => setOpen(false)}>
          <Pressable style={styles.selectSheet} onPress={() => {}}>
            <Text style={styles.selectSheetTitle}>{label}</Text>
            <ScrollView style={styles.selectList} showsVerticalScrollIndicator={false}>
              {options.map((o) => {
                const on = o === value;
                return (
                  <Pressable key={o} style={styles.selectOption} onPress={() => { onSelect(o); setOpen(false); }}>
                    <Text style={[styles.selectOptionText, on && styles.selectOptionOn]}>{o}</Text>
                    {on && <Feather name="check" size={17} color={theme.accent} />}
                  </Pressable>
                );
              })}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

function PolicyDetail({ policy, onBack, loggedIn, goLogin }: { policy: Policy; onBack: () => void; loggedIn: boolean; goLogin: () => void }) {
  const [detail, setDetail] = useState<PolicyDetailData | null>(null);
  const [liked, setLiked] = useState(false);

  useEffect(() => {
    setDetail(null);
    getPolicyDetail(policy.id).then(setDetail).catch(() => {});
  }, [policy.id]);

  useEffect(() => {
    if (!loggedIn) { setLiked(false); return; }
    getMyLikedPolicies().then((likes) => setLiked(likes.some((likedPolicy) => likedPolicy.id === policy.id))).catch(() => {});
  }, [loggedIn, policy.id]);

  const item = detail ?? policy;
  const openApplication = () => {
    Linking.openURL(item.applyUrl).catch(() => Alert.alert('열기 실패', '신청 페이지를 열지 못했습니다.'));
  };

  const toggleLike = () => {
    if (!loggedIn) {
      Alert.alert('로그인 필요', '관심 정책은 로그인 후 이용할 수 있어요.', [{ text: '취소', style: 'cancel' }, { text: '로그인', onPress: goLogin }]);
      return;
    }
    const next = !liked;
    setLiked(next);
    togglePolicyLike(policy.id).catch(() => {
      setLiked(!next);
      Alert.alert('실패', '관심 정책 저장에 실패했어요.');
    });
  };

  const hasApplicationUrl = /^https?:\/\//i.test(item.applyUrl ?? '');

  return <ScrollView contentContainerStyle={styles.page}>
    <View style={styles.detailTopBar}>
      <Back onPress={onBack} />
      <Pressable onPress={toggleLike} hitSlop={10} style={styles.policyDetailBookmark} accessibilityRole="button" accessibilityLabel="관심 정책 저장">
        <MaterialCommunityIcons name={liked ? 'bookmark' : 'bookmark-outline'} size={25} color={liked ? theme.accent : theme.textMuted} />
      </Pressable>
    </View>
    <View style={styles.badgeRow}><Badge label={item.category} publicData />{!!item.subCategory && <Badge label={item.subCategory} />}</View>
    <Text style={styles.detailTitle}>{item.title}</Text>
    <Text style={styles.detailDesc}>{item.description || item.summary}</Text>
    <View style={styles.infoBox}>
      <InfoRow label="지원 내용" value={item.benefit} />
      <InfoRow label="신청 기간" value={item.period} />
      <InfoRow label="주관 기관" value={item.institution} />
      <InfoRow label="대상 연령" value={item.targetAge} />
      {detail?.supportScale ? <InfoRow label="지원 규모" value={detail.supportScale} /> : null}
      {detail?.applicationMethod ? <InfoRow label="신청 방법" value={detail.applicationMethod} /> : null}
      {detail?.additionalCondition ? <InfoRow label="추가 자격 조건" value={detail.additionalCondition} /> : null}
      {detail?.incomeCondition ? <InfoRow label="소득 조건" value={detail.incomeCondition} /> : null}
      {detail?.documents ? <InfoRow label="제출 서류" value={detail.documents} /> : null}
      {detail?.participationRestriction ? <InfoRow label="참여 제한" value={detail.participationRestriction} /> : null}
    </View>
    {hasApplicationUrl && <Primary label="신청하러 가기" onPress={openApplication} />}
  </ScrollView>;
}

function InfoRow({ label, value }: { label: string; value: string }) { return <View><Text style={styles.infoLabel}>{label}</Text><Text style={styles.infoValue}>{value}</Text></View>; }

function GongguDetail({ item, onBack, liked, onToggleLike, loggedIn, goLogin }: {
  item: Gonggu;
  onBack: () => void;
  liked: boolean;
  onToggleLike: (id: string) => void;
  loggedIn: boolean;
  goLogin: () => void;
}) {
  const [detail, setDetail] = useState<Gonggu | null>(null);
  const [paymentOpen, setPaymentOpen] = useState(false);
  const [paying, setPaying] = useState(false);

  useEffect(() => {
    setDetail(null);
    getGongguDetail(item.id).then(setDetail).catch(() => {});
  }, [item.id]);

  const gonggu = detail ?? item;
  const currentCount = gonggu.currentCount ?? 0;
  const targetCount = gonggu.targetCount ?? 0;
  const progress = Math.max(0, Math.min(gonggu.percent, 100));
  const canJoin = gonggu.status === 'RECRUITING' || !gonggu.status;

  const toggleLike = () => {
    if (!loggedIn) {
      Alert.alert('로그인 필요', '좋아요는 로그인 후 이용할 수 있어요.', [{ text: '취소', style: 'cancel' }, { text: '로그인', onPress: goLogin }]);
      return;
    }
    onToggleLike(item.id);
  };

  const beginPayment = async () => {
    if (!loggedIn) {
      setPaymentOpen(false);
      Alert.alert('로그인 필요', '공구 참여와 결제는 로그인 후 이용할 수 있어요.', [{ text: '취소', style: 'cancel' }, { text: '로그인', onPress: goLogin }]);
      return;
    }
    setPaying(true);
    try {
      const result = await prepareGongguPayment(item.id);
      const paymentUrl = Platform.OS === 'web' ? result.nextRedirectPcUrl : (result.nextRedirectMobileUrl || result.nextRedirectPcUrl);
      if (!paymentUrl) throw new Error('결제 주소를 받지 못했습니다.');
      setPaymentOpen(false);
      await Linking.openURL(paymentUrl);
    } catch (e) {
      Alert.alert('결제 준비 실패', e instanceof Error ? e.message : '카카오페이 결제를 시작하지 못했습니다.');
    } finally {
      setPaying(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Back onPress={onBack} />
      <LinearGradient colors={[theme.cardImgA, theme.cardImgB]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.productImage}>
        {gonggu.imageUrl && <Image source={{ uri: gonggu.imageUrl }} style={styles.productRemoteImage} resizeMode="cover" />}
        <Pressable onPress={toggleLike} hitSlop={10} style={styles.detailHeart} accessibilityLabel="공구 좋아요">
          <MaterialCommunityIcons name={liked ? 'heart' : 'heart-outline'} size={24} color={liked ? theme.accent : '#fff'} />
        </Pressable>
      </LinearGradient>
      <View style={styles.gongguDetailTopline}>
        <Text style={styles.brand}>{gonggu.brand}</Text>
        {!!gonggu.writerNickname && <Text style={styles.gongguDetailWriter}>작성자 · {gonggu.writerNickname}</Text>}
      </View>
      <Text style={styles.detailTitle}>{gonggu.name}</Text>
      {!!gonggu.content && <Text style={styles.detailDesc}>{gonggu.content}</Text>}
      <View style={styles.gongguProgressCard}>
        <View style={styles.gongguProgressHead}>
          <Text style={styles.gongguParticipant}>{currentCount}/{targetCount}명 참여</Text>
          <Text style={styles.percent}>{progress}% 달성</Text>
        </View>
        <View style={styles.progress}><View style={[styles.progressFill, { width: `${progress}%` }]} /></View>
        <Text style={styles.gongguProgressHint}>{targetCount > currentCount ? `${targetCount - currentCount}명 더 모이면 공구가 성사돼요` : '목표 인원을 달성했어요'}</Text>
      </View>
      <View style={styles.gongguPriceRow}>
        <View><Text style={styles.infoLabel}>참여 금액</Text><Text style={styles.gongguPrice}>{gonggu.amount}</Text></View>
        <View style={styles.gongguDeadlineBox}><Text style={styles.infoLabel}>모집 상태</Text><Text style={styles.gongguDeadline}>{gonggu.deadline}</Text></View>
      </View>
      {!!gonggu.productUrl && <Pressable onPress={() => { void Linking.openURL(gonggu.productUrl!).catch(() => Alert.alert('링크 열기 실패', '상품 링크를 열 수 없어요.')); }} style={styles.productLinkButton} accessibilityRole="link"><Feather name="external-link" size={16} color={theme.accent} /><Text style={styles.productLinkButtonText}>상품 보러가기</Text></Pressable>}
      <Primary label={canJoin ? '공구 참여하고 결제하기' : '모집이 종료된 공구입니다'} onPress={() => setPaymentOpen(true)} disabled={!canJoin} />
      <Modal transparent visible={paymentOpen} animationType="fade" onRequestClose={() => setPaymentOpen(false)}>
        <View style={styles.modalDim}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>카카오페이로 참여할까요?</Text>
            <Text style={styles.centerCopy}>{gonggu.name}</Text>
            <Text style={styles.paymentAmount}>{gonggu.amount}</Text>
            <Text style={styles.centerCopy}>결제 완료 후 참여 인원에 반영됩니다. 목표 인원 미달 시 결제는 환불 처리됩니다.</Text>
            <Primary label={paying ? '결제 준비 중…' : '카카오페이 결제하기'} onPress={beginPayment} disabled={paying} />
            <Pressable onPress={() => setPaymentOpen(false)} disabled={paying}><Text style={styles.cancel}>돌아가기</Text></Pressable>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

function PolicyCard({ policy, onPress }: { policy: Policy; onPress: () => void }) { return <Pressable onPress={onPress} style={styles.policyCard}><View style={styles.badgeRow}><Badge label="부산시" publicData /><Badge label={policy.category} /></View><Text style={styles.policyTitle}>{policy.title}</Text><Text style={styles.policyDesc}>{policy.benefit}</Text><Text style={styles.period}>{policy.period}</Text></Pressable>; }
function Badge({ label, publicData = false }: { label: string; publicData?: boolean }) { return <View style={[styles.badge, publicData && styles.publicBadge]}><Text style={[styles.badgeText, publicData && styles.publicBadgeText]}>{label}</Text></View>; }
function Primary({ label, onPress, disabled }: { label: string; onPress: () => void; disabled?: boolean }) { return <Pressable disabled={disabled} onPress={onPress} style={[styles.primary, disabled && styles.primaryDisabled]}><Text style={styles.primaryText}>{label}</Text></Pressable>; }
function Back({ onPress }: { onPress: () => void }) { return <Pressable onPress={onPress} style={styles.back}><Feather name="chevron-left" size={20} color={theme.text} /><Text style={styles.backText}>뒤로</Text></Pressable>; }

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.background, paddingTop: Platform.OS === 'android' ? RNStatusBar.currentHeight ?? 0 : 0 },
  flex: { flex: 1 },
  skelPage: { flex: 1, paddingHorizontal: 18, paddingTop: 8 },
  skelBox: { backgroundColor: '#E4EDF2', borderRadius: 10 },
  homeScroll: { paddingBottom: 110 },
  page: { padding: 20, paddingBottom: 110, gap: 12 },

  header: { paddingHorizontal: 18, paddingTop: 8, paddingBottom: 10 },
  headerTopRow: { flexDirection: 'row', justifyContent: 'flex-end', paddingTop: 6, paddingBottom: 2 },
  bellWrap: { padding: 2 },
  bellDot: { position: 'absolute', top: 0, right: 0, width: 8, height: 8, borderRadius: 4, backgroundColor: theme.yellow },
  logo: { textAlign: 'center', color: theme.accent, fontWeight: '900', fontSize: 38, letterSpacing: -1, marginVertical: 14 },
  logoImg: { alignSelf: 'center', width: 150, height: 48, marginVertical: 12 },
  search: { flexDirection: 'row', alignItems: 'center', gap: 8, borderWidth: 2, borderColor: theme.border, borderRadius: 24, paddingHorizontal: 16, paddingVertical: 4, backgroundColor: '#fff' },
  searchInput: { flex: 1, fontSize: 14, color: theme.text, paddingVertical: 8 },
  searchPlaceholder: { flex: 1, fontSize: 14, color: theme.textMuted, paddingVertical: 8 },
  searchTopRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 16, paddingTop: 10, paddingBottom: 8 },
  searchBox: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: theme.surface, borderRadius: 14, paddingHorizontal: 14, paddingVertical: 4 },
  searchBoxInput: { flex: 1, fontSize: 15, color: theme.text, paddingVertical: 10 },
  recentHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, marginTop: 18, marginBottom: 12 },
  recentTitle: { fontSize: 16, fontWeight: '800', color: theme.text },
  recentClear: { fontSize: 13, color: theme.textFaint },
  recentEmpty: { paddingHorizontal: 20, fontSize: 13, color: theme.textFaint },
  recentWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, paddingHorizontal: 20 },
  recentChip: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderColor: theme.border, borderRadius: 20, paddingLeft: 14, paddingRight: 10, paddingVertical: 8 },
  recentChipText: { fontSize: 14, fontWeight: '600', color: theme.text },
  ranking: { alignSelf: 'center', width: '82%', flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 2, paddingTop: 12, paddingBottom: 4 },
  rankNum: { color: theme.accent, fontWeight: '700', fontSize: 13 },
  rankText: { flex: 1, color: '#5F7482', fontSize: 13 },
  rankingModalDim: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,.42)' },
  rankingModalCard: { maxHeight: '78%', backgroundColor: theme.background, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 20, paddingBottom: 28 },
  rankingModalHead: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 12 },
  rankingModalTitle: { fontSize: 19, fontWeight: '900', color: theme.text },
  rankingModalSub: { fontSize: 12, color: theme.textMuted, marginTop: 4 },
  rankingModalList: { maxHeight: 460 },
  rankingPolicyRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 14, borderBottomWidth: 1, borderColor: theme.surfaceAlt },
  rankingPolicyNumber: { width: 20, textAlign: 'center', color: theme.accent, fontSize: 15, fontWeight: '900' },
  rankingPolicyCopy: { flex: 1, gap: 4 },
  rankingPolicyTitle: { color: theme.text, fontSize: 14, fontWeight: '700' },
  rankingPolicyMeta: { color: theme.textMuted, fontSize: 11.5 },
  rankingEmpty: { paddingVertical: 32, textAlign: 'center', color: theme.textMuted, fontSize: 13 },

  section: { paddingHorizontal: 18, paddingTop: 10 },
  policySection: { borderTopWidth: 2, borderStyle: 'dashed', borderColor: theme.border, marginTop: 12, paddingTop: 14 },
  sectionHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 },
  sectionTitle: { fontSize: 18, fontWeight: '800' },
  hint: { fontSize: 11, color: theme.textFaint },
  pill: { borderWidth: 1, borderColor: theme.border, borderRadius: 20, paddingHorizontal: 11, paddingVertical: 4 },
  pillText: { fontSize: 12 },

  carousel: { gap: 12, paddingVertical: 10, paddingRight: 6 },
  gongguCard: { width: 150 },
  gongguWide: { width: '100%', marginBottom: 4 },
  gongguImg: { width: 150, height: 150, borderRadius: 10, padding: 8, alignItems: 'flex-end', overflow: 'hidden' },
  gongguImgWide: { width: '100%', height: 200 },
  gongguRemoteImage: { ...StyleSheet.absoluteFill },
  gongguWriter: { color: theme.textMuted, fontSize: 12, marginTop: -4 },
  heart: {},
  gongguHeart: { position: 'absolute', top: 10, right: 10, zIndex: 2, width: 30, height: 30, borderRadius: 15, backgroundColor: 'rgba(0,0,0,0.25)', alignItems: 'center', justifyContent: 'center' },
  brand: { fontSize: 11, color: theme.textFaint, marginTop: 8 },
  gongguName: { fontSize: 13, fontWeight: '700', lineHeight: 18, marginTop: 2 },
  gongguMeta: { fontSize: 11, color: theme.textMuted, marginTop: 6 },
  percent: { fontSize: 14, fontWeight: '800', color: theme.accent, marginTop: 2 },

  moreCard: { width: 150, height: 150, borderWidth: 2, borderStyle: 'dashed', borderColor: theme.border, borderRadius: 10, backgroundColor: theme.surface, alignItems: 'center', justifyContent: 'center' },
  moreTitle: { fontSize: 12, fontWeight: '700', marginTop: 6 },
  moreSub: { fontSize: 10, color: '#5F7482', marginTop: 2 },

  policyRow: { paddingVertical: 12, gap: 5 },
  policyRowDivider: { borderBottomWidth: 1, borderStyle: 'dashed', borderColor: theme.divider },
  tag: { alignSelf: 'flex-start', backgroundColor: theme.surfaceAlt, borderRadius: 20, paddingHorizontal: 10, paddingVertical: 3 },
  tagText: { fontSize: 11, fontWeight: '700', color: '#24516F' },
  tagVulnerable: { backgroundColor: '#FDE8EC' },
  tagTextVulnerable: { color: '#D9485F' },
  policyRowTitle: { fontSize: 15, fontWeight: '800' },
  policyRowDesc: { fontSize: 12, color: '#5F7482' },
  policyRowMore: { fontSize: 12, color: theme.accent, fontWeight: '700' },

  notifBackdrop: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 },
  notifPanel: { position: 'absolute', top: 44, right: 16, width: 272, backgroundColor: '#fff', borderWidth: 1, borderColor: theme.surfaceAlt, borderRadius: 14, overflow: 'hidden', shadowColor: '#173B57', shadowOpacity: 0.18, shadowRadius: 20, shadowOffset: { width: 0, height: 8 }, elevation: 8 },
  notifHead: { paddingHorizontal: 14, paddingVertical: 12, borderBottomWidth: 1, borderColor: theme.surfaceAlt, fontSize: 13, fontWeight: '700' },
  notifList: { maxHeight: 320 },
  notifEmpty: { paddingHorizontal: 14, paddingVertical: 22, alignItems: 'center' },
  notifItem: { paddingHorizontal: 14, paddingVertical: 11, borderBottomWidth: 1, borderColor: '#E8EFF3' },
  notifItemLast: { borderBottomWidth: 0 },
  notifTitle: { fontSize: 12.5, fontWeight: '700' },
  notifTitleMuted: { color: theme.textMuted },
  notifBold: { fontWeight: '700', color: theme.text },
  notifBody: { fontSize: 11.5, color: theme.textMuted, marginTop: 3, lineHeight: 17 },
  notifTime: { fontSize: 10, color: '#8C9CA6', marginTop: 4 },

  polHeader: { paddingHorizontal: 18, paddingTop: 12 },
  polTitle: { fontSize: 22, fontWeight: '700', marginBottom: 14 },
  polCats: { gap: 8, paddingBottom: 12 },
  filterBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, borderWidth: 1, borderColor: theme.border, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 11, backgroundColor: theme.surfaceWhite, marginTop: 12, marginBottom: 12 },
  filterBtnText: { fontSize: 13.5, fontWeight: '700', color: theme.text },
  sheetDim: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,.42)' },
  sheet: { backgroundColor: theme.surfaceWhite, borderTopLeftRadius: 24, borderTopRightRadius: 24, paddingTop: 16, paddingBottom: 24 },
  sheetHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingBottom: 8 },
  sheetTitle: { fontSize: 17, fontWeight: '800', color: theme.text },
  sheetReset: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  sheetResetText: { fontSize: 13, color: theme.textMuted, fontWeight: '600' },
  sheetList: { maxHeight: 360, paddingHorizontal: 12 },
  sheetOption: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 15, borderRadius: 10, marginVertical: 2 },
  sheetOptionOn: { backgroundColor: theme.blueBg },
  sheetOptionText: { fontSize: 15, color: theme.text },
  sheetOptionTextOn: { color: theme.accentDark, fontWeight: '800' },
  sheetDivider: { height: 1, backgroundColor: theme.divider, marginTop: 8 },
  sheetApply: { backgroundColor: theme.accent, marginHorizontal: 20, marginTop: 16, borderRadius: 12, paddingVertical: 16, alignItems: 'center' },
  sheetApplyText: { color: '#fff', fontSize: 15, fontWeight: '800' },
  polMetaRow: { marginTop: 2, marginBottom: 10, gap: 6 },
  polCount: { fontSize: 12.5, color: '#5F7482' },
  polCountNum: { color: theme.accent, fontWeight: '700' },
  sortRow: { flexDirection: 'row', gap: 6 },
  sortChip: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 14 },
  sortChipOn: { backgroundColor: '#DCEFFA' },
  sortChipText: { fontSize: 10.5, fontWeight: '700', color: theme.textFaint },
  sortChipTextOn: { color: theme.accent },
  polListPad: { paddingHorizontal: 18, paddingBottom: 110 },
  polItem: { paddingVertical: 14, borderBottomWidth: 1, borderColor: theme.surfaceAlt },
  polBookmark: { position: 'absolute', top: 14, right: 0, zIndex: 2 },
  polItemTitle: { fontSize: 14.5, fontWeight: '700', marginTop: 6, paddingRight: 26, lineHeight: 20 },
  polItemSummary: { fontSize: 12, color: '#5F7482', marginTop: 3 },
  polItemInstitution: { fontSize: 11, color: theme.textFaint, marginTop: 6 },
  polItemBottom: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 8 },
  polDeadline: { fontSize: 11.5, fontWeight: '700', color: theme.accent },
  polItemMore: { fontSize: 11.5, fontWeight: '700', color: theme.accent },
  polEmpty: { alignItems: 'center', paddingVertical: 70, paddingHorizontal: 20 },
  polEmptyText: { fontSize: 13.5, color: '#5F7482', marginBottom: 14 },
  resetBtn: { borderWidth: 1, borderColor: theme.border, borderRadius: 20, paddingHorizontal: 18, paddingVertical: 8 },
  resetBtnText: { fontSize: 12.5, fontWeight: '700' },
  screenHeader: { padding: 20, paddingBottom: 10 },
  screenTitle: { fontSize: 25, fontWeight: '900' },
  subtitle: { color: theme.textMuted, marginTop: 5, lineHeight: 20 },
  gongguListHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  gongguCreateButton: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 10, borderRadius: 10, backgroundColor: theme.accent },
  gongguCreateButtonText: { color: '#fff', fontSize: 12, fontWeight: '800' },
  gongguCreateSheet: { maxHeight: '86%', backgroundColor: theme.background, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 22, paddingBottom: 30 },
  gongguCreateSheetHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 },
  gongguFormLabel: { marginTop: 12, marginBottom: 6, color: theme.text, fontSize: 13, fontWeight: '800' },
  gongguFormInput: { borderWidth: 1, borderColor: theme.border, borderRadius: 10, backgroundColor: '#fff', paddingHorizontal: 13, paddingVertical: 12, color: theme.text, fontSize: 14 },
  gongguFormTextarea: { minHeight: 96 },
  gongguImagePicker: { height: 92, borderWidth: 1, borderStyle: 'dashed', borderColor: theme.accent, borderRadius: 10, backgroundColor: '#EFF8FD', alignItems: 'center', justifyContent: 'center', gap: 6 },
  gongguImagePickerText: { color: theme.accent, fontSize: 13, fontWeight: '800' },
  gongguImagePreviewWrap: { position: 'relative', height: 180, borderRadius: 10, overflow: 'hidden', backgroundColor: theme.surface },
  gongguImagePreview: { width: '100%', height: '100%' },
  gongguImageRemove: { position: 'absolute', top: 8, right: 8, width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(0,0,0,.55)' },
  gongguImageChange: { position: 'absolute', bottom: 8, right: 8, borderRadius: 16, backgroundColor: 'rgba(0,0,0,.58)', paddingHorizontal: 11, paddingVertical: 7 },
  gongguImageChangeText: { color: '#fff', fontSize: 12, fontWeight: '800' },
  gongguFormHint: { marginTop: 12, color: theme.textMuted, fontSize: 11.5, lineHeight: 17 },
  chips: { paddingHorizontal: 20, paddingBottom: 10, gap: 8 },
  chip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, backgroundColor: theme.surface },
  chipOn: { backgroundColor: theme.accent },
  chipTextOn: { color: '#fff', fontWeight: '700' },
  list: { padding: 20, paddingTop: 5, gap: 12, paddingBottom: 110 },

  policyCard: { backgroundColor: '#fff', padding: 16, borderRadius: 15, gap: 7, borderWidth: 1, borderColor: theme.divider },
  badgeRow: { flexDirection: 'row', gap: 5 },
  badge: { alignSelf: 'flex-start', backgroundColor: theme.surface, paddingHorizontal: 7, paddingVertical: 3, borderRadius: 6 },
  badgeText: { fontSize: 11, color: theme.textMuted },
  publicBadge: { backgroundColor: '#DCEFFA' },
  publicBadgeText: { color: '#2E70A8' },
  policyTitle: { fontWeight: '800', fontSize: 16 },
  policyDesc: { color: theme.text, fontSize: 13 },
  period: { color: theme.textMuted, fontSize: 12, marginTop: 4 },

  centerPage: { flex: 1, padding: 28, justifyContent: 'center', alignItems: 'center', gap: 16 },
  heroTitle: { fontSize: 25, fontWeight: '900', textAlign: 'center', lineHeight: 35 },
  centerCopy: { textAlign: 'center', color: theme.textMuted, lineHeight: 21 },
  primary: { backgroundColor: theme.accent, borderRadius: 14, padding: 17, alignSelf: 'stretch', alignItems: 'center', marginTop: 12 },
  primaryDisabled: { backgroundColor: '#D8E3E9' },
  primaryText: { color: '#fff', fontWeight: '800' },
  loading: { color: theme.accent, fontSize: 22, letterSpacing: 5 },
  segment: { flexDirection: 'row', backgroundColor: theme.surface, padding: 4, borderRadius: 10, marginTop: 10 },
  segmentItem: { flex: 1, padding: 10, alignItems: 'center', borderRadius: 8 },
  segmentOn: { backgroundColor: '#fff' },
  segmentTextOn: { fontWeight: '800', color: theme.accent },
  credit: { backgroundColor: '#fff', borderRadius: 18, padding: 30, alignItems: 'center', gap: 13, borderWidth: 1, borderColor: theme.divider },
  creditScore: { color: theme.accent, fontSize: 38, fontWeight: '900' },

  input: { alignSelf: 'stretch', padding: 15, borderRadius: 12, backgroundColor: '#fff' },
  selectWrap: { alignSelf: 'stretch' },
  select: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 15, paddingVertical: 15, borderRadius: 12, borderWidth: 1, borderColor: theme.border, backgroundColor: '#fff' },
  selectValue: { fontSize: 15, fontWeight: '700', color: theme.text },
  selectPlaceholder: { fontSize: 15, color: theme.textMuted },
  selectDim: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,.42)' },
  selectSheet: { backgroundColor: theme.background, borderTopLeftRadius: 24, borderTopRightRadius: 24, paddingHorizontal: 20, paddingTop: 18, paddingBottom: 28 },
  selectSheetTitle: { fontSize: 15, fontWeight: '800', marginBottom: 8 },
  selectList: { maxHeight: 340 },
  selectOption: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 15, borderBottomWidth: 1, borderColor: theme.surfaceAlt },
  selectOptionText: { fontSize: 15, color: theme.text },
  selectOptionOn: { color: theme.accent, fontWeight: '800' },
  profile: { backgroundColor: '#fff', borderRadius: 16, padding: 18, flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 10, borderWidth: 1, borderColor: theme.divider },
  avatar: { backgroundColor: theme.accent, color: '#fff', borderRadius: 40, width: 44, height: 44, textAlign: 'center', textAlignVertical: 'center', fontWeight: '800' },
  profileName: { fontSize: 16, fontWeight: '800' },
  formLabel: { color: theme.textMuted, fontSize: 12, fontWeight: '700', marginTop: 4 },
  formInput: { borderWidth: 1, borderColor: theme.divider, borderRadius: 10, backgroundColor: '#fff', paddingHorizontal: 13, paddingVertical: 11, fontSize: 14, color: theme.text },
  menu: { backgroundColor: '#fff', padding: 18, borderRadius: 12, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', borderWidth: 1, borderColor: theme.divider },
  logout: { textAlign: 'center', color: theme.textMuted, marginTop: 20 },

  back: { flexDirection: 'row', alignItems: 'center', alignSelf: 'flex-start', paddingVertical: 8 },
  backText: { marginLeft: 2 },
  detailTopBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  policyDetailBookmark: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center', backgroundColor: theme.surface },
  detailTitle: { fontSize: 25, fontWeight: '900', lineHeight: 34 },
  detailDesc: { color: theme.textMuted, lineHeight: 22 },
  infoBox: { backgroundColor: '#fff', borderRadius: 15, padding: 18, gap: 6, marginTop: 10, borderWidth: 1, borderColor: theme.divider },
  infoLabel: { fontSize: 12, color: theme.textMuted, marginTop: 4 },
  infoValue: { fontWeight: '700', marginTop: 3, marginBottom: 12, lineHeight: 21 },
  productImage: { height: 220, borderRadius: 14, alignItems: 'flex-end', padding: 12, overflow: 'hidden' },
  productRemoteImage: { ...StyleSheet.absoluteFill },
  detailHeart: { zIndex: 1, width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(0,0,0,0.24)', alignItems: 'center', justifyContent: 'center' },
  gongguDetailTopline: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  gongguDetailWriter: { color: theme.textMuted, fontSize: 13, fontWeight: '600' },
  gongguProgressCard: { backgroundColor: theme.surface, borderRadius: 14, padding: 15, gap: 9 },
  gongguProgressHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  gongguParticipant: { color: theme.text, fontSize: 16, fontWeight: '800' },
  gongguProgressHint: { color: theme.textMuted, fontSize: 12 },
  gongguPriceRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end', backgroundColor: '#fff', borderWidth: 1, borderColor: theme.border, borderRadius: 14, padding: 15 },
  gongguPrice: { color: theme.accent, fontSize: 22, fontWeight: '900' },
  productLinkButton: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7, borderWidth: 1, borderColor: theme.accent, borderRadius: 12, paddingVertical: 13, backgroundColor: '#EFF8FD' },
  productLinkButtonText: { color: theme.accent, fontSize: 14, fontWeight: '800' },
  gongguDeadlineBox: { alignItems: 'flex-end' },
  gongguDeadline: { color: theme.text, fontSize: 14, fontWeight: '700' },
  paymentAmount: { color: theme.accent, fontSize: 25, fontWeight: '900', textAlign: 'center' },
  progress: { height: 8, backgroundColor: theme.surface, borderRadius: 8, overflow: 'hidden', marginTop: 7 },
  progressFill: { height: '100%', backgroundColor: theme.accent },
  modalDim: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,.42)' },
  modalCard: { backgroundColor: theme.background, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 25, gap: 12 },
  modalTitle: { fontSize: 21, fontWeight: '900', textAlign: 'center' },
  cancel: { textAlign: 'center', padding: 13, color: theme.textMuted },

  tabBar: { position: 'absolute', bottom: 0, left: 0, right: 0, height: 76, backgroundColor: '#fff', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around', paddingHorizontal: 8, borderTopLeftRadius: 22, borderTopRightRadius: 22, shadowColor: '#173B57', shadowOpacity: 0.12, shadowRadius: 10, shadowOffset: { width: 0, height: -2 }, elevation: 12 },
  nav: { alignItems: 'center', gap: 3, minWidth: 52 },
  navLabel: { fontSize: 11, marginTop: 2 },
  fabSlot: { width: 64 },
  fab: { position: 'absolute', left: '50%', marginLeft: -38, top: -4, width: 76, height: 76, borderRadius: 24, backgroundColor: theme.accent, alignItems: 'center', justifyContent: 'center', borderWidth: 8, borderColor: theme.background, shadowColor: '#173B57', shadowOpacity: 0.22, shadowRadius: 10, shadowOffset: { width: 0, height: 4 }, elevation: 10 },
  fabActive: { backgroundColor: theme.accentDark },
  fabLabel: { color: '#fff', fontWeight: '700', fontSize: 10.5, marginTop: 1 },

  // Recommendation flow
  // 하단 고정 다운로드/저장 바(탭 바 포함)가 마지막 AI 리포트를 덮지 않도록 충분한 스크롤 여백을 둔다.
  recPage: { padding: 22, paddingBottom: 210, flexGrow: 1 },
  recHeadRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 14 },
  recKicker: { fontSize: 12, color: theme.textFaint },
  recReset: { fontSize: 12, color: theme.textMuted, textDecorationLine: 'underline' },
  recTitle: { fontSize: 21, fontWeight: '800', lineHeight: 30, marginBottom: 8 },
  recSub: { fontSize: 12, color: '#5F7482', lineHeight: 18 },
  recLabel: { fontSize: 12, fontWeight: '700', color: '#5F7482', marginTop: 18, marginBottom: 10 },
  chipWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  selChip: { paddingHorizontal: 14, paddingVertical: 9, borderRadius: 20, backgroundColor: theme.surface },
  selChipOn: { backgroundColor: theme.text },
  selChipText: { fontSize: 12.5, fontWeight: '700', color: '#5F7482' },
  selChipTextOn: { color: '#fff' },
  subChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 13, paddingVertical: 9, borderRadius: 20, borderWidth: 1, borderColor: theme.divider, backgroundColor: '#fff' },
  subChipOn: { borderColor: theme.accent, backgroundColor: '#DCEFFA' },
  subChipText: { fontSize: 12.5, fontWeight: '600', color: theme.textMuted },
  subChipTextOn: { color: theme.accent, fontWeight: '700' },
  recBtn: { marginTop: 28, alignItems: 'center', paddingVertical: 15, borderRadius: 12 },
  recBtnOn: { backgroundColor: theme.text },
  recBtnOff: { backgroundColor: theme.surfaceAlt },
  recBtnTextOn: { color: '#fff', fontSize: 14, fontWeight: '700' },
  recBtnTextOff: { color: '#8C9CA6', fontSize: 14, fontWeight: '700' },

  creditBox: { borderWidth: 2, borderColor: theme.surfaceAlt, borderRadius: 14, padding: 16, marginTop: 20, marginBottom: 16 },
  creditTitle: { fontSize: 14, fontWeight: '700', marginBottom: 6 },
  creditBtn: { backgroundColor: theme.accent, borderRadius: 10, paddingVertical: 12, alignItems: 'center', marginTop: 14 },
  creditBtnDisabled: { opacity: 0.55 },
  creditBtnText: { color: '#fff', fontSize: 13, fontWeight: '700' },
  creditLinkedRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  linkedBadge: { backgroundColor: '#DFF5EE', borderRadius: 20, paddingHorizontal: 9, paddingVertical: 3 },
  linkedBadgeText: { fontSize: 11, fontWeight: '700', color: '#357F6C' },
  creditUpdated: { fontSize: 11, color: theme.textMuted, marginBottom: 12 },
  creditOutlineBtn: { borderWidth: 1, borderColor: theme.border, borderRadius: 10, paddingVertical: 11, alignItems: 'center' },
  creditOutlineText: { fontSize: 13, fontWeight: '700' },

  editField: { borderWidth: 1, borderStyle: 'dashed', borderColor: theme.divider, borderRadius: 12, padding: 14, marginBottom: 10 },
  editFieldHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  editFieldValue: { fontSize: 15, fontWeight: '700', marginTop: 2 },

  stepDots: { flexDirection: 'row', gap: 8, marginBottom: 22, marginTop: 4 },
  stepDot: { flex: 1, height: 6, borderRadius: 4, backgroundColor: '#D8E3E9' },
  stepDotOn: { backgroundColor: theme.accent },
  skeleton: { height: 88, borderRadius: 12, backgroundColor: '#E4EDF2', marginBottom: 14 },
  aiLoadingWrap: { gap: 12 },
  aiLoadingStatus: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingBottom: 8 },
  aiLoadingDot: { width: 9, height: 9, borderRadius: 5, backgroundColor: theme.accent },
  aiLoadingTitle: { fontSize: 17, fontWeight: '900', color: theme.text },
  aiLoadingCopy: { marginTop: 3, fontSize: 12, color: theme.textMuted },
  aiLoadingScoreCard: { borderWidth: 1, borderColor: theme.surfaceAlt, borderRadius: 14, padding: 16, backgroundColor: '#fff' },
  aiLoadingLabel: { fontSize: 13, fontWeight: '800', color: theme.textMuted, marginBottom: 14 },
  aiLoadingScoreRow: { flexDirection: 'row', alignItems: 'center', gap: 15 },
  aiLoadingCircle: { width: 70, height: 70, borderRadius: 35, marginBottom: 0 },
  aiLoadingScoreLines: { flex: 1, gap: 9 },
  aiLoadingLineLong: { height: 17, width: '72%', borderRadius: 6, marginBottom: 0 },
  aiLoadingLineShort: { height: 11, width: '44%', borderRadius: 5, marginBottom: 0 },
  aiLoadingSectionHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 8 },
  aiLoadingSectionTitle: { fontSize: 15, fontWeight: '900', color: theme.text },
  aiLoadingTinyLine: { height: 10, width: 46, borderRadius: 5, marginBottom: 0 },
  aiLoadingPolicyCard: { borderWidth: 1, borderColor: theme.surfaceAlt, borderRadius: 14, padding: 14, backgroundColor: '#fff', gap: 9 },
  aiLoadingTag: { height: 18, width: 52, borderRadius: 12, marginBottom: 0 },
  aiLoadingPolicyTitle: { height: 17, width: '74%', borderRadius: 6, marginBottom: 0 },
  aiLoadingPolicyCopy: { height: 12, width: '92%', borderRadius: 5, marginBottom: 0 },
  aiLoadingReason: { height: 30, width: '100%', borderRadius: 8, marginBottom: 0, backgroundColor: '#DCECF6' },

  gaugeBox: { borderWidth: 2, borderColor: theme.surfaceAlt, borderRadius: 14, padding: 16, marginTop: 6, marginBottom: 18 },
  scoreBoxTitle: { fontSize: 15, fontWeight: '900', color: theme.text, marginBottom: 12 },
  scoreBoxContent: { flexDirection: 'row', alignItems: 'center', gap: 16 },
  gaugeRing: { width: 82, height: 82, borderRadius: 41, alignItems: 'center', justifyContent: 'center' },
  gaugeSegment: { position: 'absolute', width: 3, height: 9, borderRadius: 2, left: 39.5, top: 36.5 },
  gaugeSegmentOff: { backgroundColor: '#DCE7EC' },
  gaugeInner: { width: 56, height: 56, borderRadius: 28, backgroundColor: '#fff', alignItems: 'center', justifyContent: 'center' },
  gaugeScore: { fontSize: 18, fontWeight: '700' },
  gaugeUnit: { fontSize: 8.5, color: theme.textMuted, marginTop: -1 },
  gaugeGrade: { fontSize: 16, fontWeight: '700', color: theme.accent, marginTop: 2 },

  recCard: { borderWidth: 1, borderColor: theme.surfaceAlt, borderRadius: 14, padding: 14, marginBottom: 12 },
  recommendationSection: { marginTop: 4, marginBottom: 8 },
  recommendationSectionHead: { marginBottom: 12 },
  recommendationSectionTitle: { fontSize: 18, fontWeight: '900', color: theme.text },
  recommendationSectionSub: { marginTop: 4, fontSize: 12, color: theme.textMuted },
  recommendationToggle: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 11, borderRadius: 10, backgroundColor: '#EFF8FD' },
  recommendationToggleText: { color: theme.accent, fontSize: 13, fontWeight: '800' },
  bookmark: { position: 'absolute', top: 12, right: 12, zIndex: 2 },
  recCardTitle: { fontSize: 14.5, fontWeight: '700', marginTop: 6, paddingRight: 26 },
  recCardSummary: { fontSize: 12, color: '#5F7482', marginTop: 3 },
  reasonBox: { backgroundColor: '#EFF8FD', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8, marginTop: 9 },
  reasonText: { fontSize: 11.5, color: theme.textMuted, lineHeight: 16 },
  recCardCaution: { fontSize: 11, color: theme.textFaint, lineHeight: 16, marginTop: 8 },
  impactText: { fontSize: 11.5, fontWeight: '700', marginTop: 8 },
  insightCard: { backgroundColor: '#F3FAFE', borderRadius: 14, padding: 16, marginTop: 8, gap: 10 },
  aiReportSection: { marginTop: 22 },
  aiReportSectionTitle: { fontSize: 18, fontWeight: '900', color: theme.text },
  aiReportSectionSub: { marginTop: 4, fontSize: 12, color: theme.textMuted },
  insightHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  insightTitle: { fontSize: 16, fontWeight: '800', color: theme.text },
  insightMeta: { fontSize: 11, fontWeight: '700', color: theme.accent },
  insightSummary: { fontSize: 13, color: theme.text, lineHeight: 20 },
  insightRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: '#fff', borderRadius: 8, padding: 10 },
  insightLabel: { fontSize: 12, color: theme.textMuted },
  insightValue: { fontSize: 13, fontWeight: '800', color: theme.accent },
  insightItem: { gap: 4 },
  insightItemTitle: { fontSize: 12, fontWeight: '800', color: theme.text },
  insightItemText: { fontSize: 12, lineHeight: 18, color: theme.textMuted },
  insightEvidence: { fontSize: 11, lineHeight: 16, color: theme.textFaint },
  insightFoot: { fontSize: 10.5, lineHeight: 15, color: theme.textFaint },
  insightToggle: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 3, paddingHorizontal: 9, paddingVertical: 6, borderRadius: 10, backgroundColor: '#fff' },
  insightToggleText: { color: theme.accent, fontSize: 12, fontWeight: '800' },
  policySheet: { position: 'absolute', left: 12, right: 12, bottom: 154, maxHeight: 64, overflow: 'hidden', borderRadius: 18, backgroundColor: '#fff', borderWidth: 1, borderColor: theme.divider, shadowColor: '#173B57', shadowOpacity: 0.16, shadowRadius: 12, shadowOffset: { width: 0, height: 3 }, elevation: 9 },
  policySheetOpen: { maxHeight: 350 },
  policySheetHeader: { minHeight: 64, paddingHorizontal: 17, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  policySheetTitle: { fontSize: 15, fontWeight: '800', color: theme.text },
  policySheetSub: { fontSize: 11.5, color: theme.textMuted, marginTop: 3 },
  policySheetList: { paddingHorizontal: 12, paddingBottom: 12 },
  savedResultHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  savedResultScore: { color: theme.accent, fontSize: 17, fontWeight: '900' },
  savedReportDownload: { alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12, marginBottom: 18, paddingHorizontal: 12, paddingVertical: 9, borderRadius: 10, backgroundColor: '#EFF8FD', borderWidth: 1, borderColor: theme.divider },
  savedReportDownloadText: { color: theme.accent, fontSize: 12, fontWeight: '800' },

  introPage: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  introLineWrap: { marginTop: 6 },
  introTitle: { fontSize: 21, fontWeight: '800', textAlign: 'center', lineHeight: 31 },
  introGate: { alignSelf: 'stretch', alignItems: 'center', marginTop: 30 },
  introGateSub: { fontSize: 13, color: theme.textMuted, marginBottom: 14 },
  introLoginBtn: { alignSelf: 'stretch', backgroundColor: theme.accent, borderRadius: 14, paddingVertical: 16, alignItems: 'center' },
  introLoginText: { color: '#fff', fontSize: 15, fontWeight: '800' },

  saveBarInline: { marginTop: 20, marginHorizontal: -22, paddingHorizontal: 22, paddingTop: 12, paddingBottom: 18, backgroundColor: theme.background, borderTopWidth: 1, borderColor: theme.surfaceAlt, alignItems: 'center' },
  resultActionRow: { flexDirection: 'row', alignItems: 'center', gap: 8, alignSelf: 'stretch' },
  saveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, alignSelf: 'stretch', backgroundColor: theme.accent, borderRadius: 12, paddingVertical: 15 },
  saveBtnGrow: { flex: 1 },
  saveBtnDone: { backgroundColor: '#357F6C' },
  downloadBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5, borderWidth: 1, borderColor: theme.accent, backgroundColor: '#fff', borderRadius: 11, paddingHorizontal: 11, paddingVertical: 12 },
  downloadBtnText: { color: theme.accent, fontSize: 12, fontWeight: '800' },
  saveInfoButton: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center', backgroundColor: '#EFF8FD', borderWidth: 1, borderColor: theme.divider },
  actionDisabled: { opacity: 0.55 },
  saveBtnText: { color: '#fff', fontSize: 14, fontWeight: '800' },

  aiCard: { borderWidth: 1.5, borderColor: theme.accent, borderRadius: 14, padding: 16, marginTop: 6, backgroundColor: '#EFF8FD' },
  aiHead: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10 },
  aiTitle: { fontSize: 14, fontWeight: '800' },
  kcbBadge: { marginLeft: 'auto', backgroundColor: theme.accent, borderRadius: 20, paddingHorizontal: 9, paddingVertical: 3 },
  kcbBadgeText: { fontSize: 10.5, fontWeight: '700', color: '#fff' },
  aiBody: { fontSize: 12.5, color: '#5F7482', lineHeight: 20 },
  aiStrong: { fontWeight: '700', color: theme.text },
  aiDeltaRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 14, paddingTop: 12, borderTopWidth: 1, borderStyle: 'dashed', borderColor: theme.divider },
  aiDeltaLabel: { fontSize: 12, color: theme.textMuted },
  aiDelta: { fontSize: 20, fontWeight: '900', color: theme.accent },
  aiFoot: { fontSize: 10.5, color: theme.textFaint, marginTop: 8, lineHeight: 15 },
});
