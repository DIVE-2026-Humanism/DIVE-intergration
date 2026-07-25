package com.jabgonggu.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * 근무 지역(단일 선택) 필터 바텀시트.
 *
 * Stateless: 선택 상태(selectedRegion)는 상위(ViewModel StateFlow / rememberSaveable)에서 관리하고
 * 콜백으로만 통신한다. 바깥 탭·스와이프 다운은 취소(onDismiss)로 처리하며, 선택 반영은
 * "적용하기"를 눌렀을 때만 onApply로 확정한다.
 *
 * @param regions          지역 목록
 * @param selectedRegion   현재 선택된 지역(없으면 null)
 * @param onRegionSelected 항목 선택/초기화 시 호출 (초기화는 null)
 * @param onApply          "적용하기" 클릭 — 상위에서 값 확정 + 시트 닫기 처리
 * @param onDismiss        바깥 탭/스와이프 다운/취소
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RegionFilterBottomSheet(
    regions: List<String>,
    selectedRegion: String?,
    onRegionSelected: (String?) -> Unit,
    onApply: () -> Unit,
    onDismiss: () -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = MaterialTheme.colorScheme.surface,
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {

            // 상단: 타이틀 + 초기화
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text = "근무 지역",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                TextButton(onClick = { onRegionSelected(null) }) {
                    Icon(
                        imageVector = Icons.Filled.Refresh,
                        contentDescription = null,
                        modifier = Modifier.padding(end = 4.dp),
                    )
                    Text("초기화")
                }
            }

            // 중단: 스크롤 가능한 지역 리스트 (단일 선택, 라디오 동작)
            LazyColumn(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 420.dp)
                    .weight(1f, fill = false),
                contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                items(regions, key = { it }) { region ->
                    val selected = region == selectedRegion
                    RegionRow(
                        region = region,
                        selected = selected,
                        onClick = { onRegionSelected(region) },
                    )
                }
            }

            // 하단: 구분선 + 고정 "적용하기" 버튼
            HorizontalDivider(
                thickness = 1.dp,
                color = MaterialTheme.colorScheme.outlineVariant,
            )
            Button(
                onClick = onApply,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 16.dp),
                shape = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.buttonColors(
                    // 앱 테마의 브랜드(그린/오션블루)를 primary로 설정해 사용 — 하드코딩 지양
                    containerColor = MaterialTheme.colorScheme.primary,
                    contentColor = MaterialTheme.colorScheme.onPrimary,
                ),
            ) {
                Text(
                    text = "적용하기",
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(vertical = 4.dp),
                )
            }
        }
    }
}

@Composable
private fun RegionRow(
    region: String,
    selected: Boolean,
    onClick: () -> Unit,
) {
    val bg = if (selected) MaterialTheme.colorScheme.primaryContainer else Color.Transparent
    val fg = if (selected) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurface

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .selectable(
                selected = selected,
                onClick = onClick,
                role = Role.RadioButton, // 접근성: 라디오 버튼으로 노출
            )
            .background(bg, RoundedCornerShape(10.dp))
            .padding(horizontal = 16.dp, vertical = 14.dp),
    ) {
        Text(
            text = region,
            color = fg,
            fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
            style = MaterialTheme.typography.bodyLarge,
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Preview(showBackground = true)
@Composable
private fun RegionFilterBottomSheetPreview() {
    val regions = listOf(
        "서울", "경기", "인천", "부산", "대구", "대전",
        "광주", "울산", "세종", "강원", "경남", "경북",
        "전남", "전북", "충남", "충북", "제주",
    )
    MaterialTheme {
        // Preview에서는 시트 내부 콘텐츠만 렌더링해 확인 (실제 사용 시 ModalBottomSheet로 감쌈)
        RegionFilterBottomSheet(
            regions = regions,
            selectedRegion = "부산",
            onRegionSelected = {},
            onApply = {},
            onDismiss = {},
        )
    }
}
