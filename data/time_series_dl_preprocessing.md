# 시계열 딥러닝 전처리 가이드

## 1. 현재 디렉터리 자산 개요

| 경로 | 주요 내용 | 활용 포인트 |
| --- | --- | --- |
| `all_data_info/` | `analysis_summary.*`, `data_profile_summary.*`, `column_structure.*` 메타데이터 | 결측·자료형·컬럼 스키마를 빠르게 파악 |
| `columns_mean_json_en/`, `columns_mean_json_ko/` | 36개 CSV별 컬럼 의미 설명 (영/한) | 컬럼 해석, 피처 엔지니어링 시 참조 |
| `data_csv_type/` | 원본 CSV 36개 | 시계열/설문/순위/정적 스냅샷 데이터 원천 |
| `데이터_정리_후_codex_결과물/` | 이전 분석 메모 및 전략 문서 | 기존 인사이트·업무 히스토리 파악 |

> 참고: CSV 파일은 모두 UTF-8(BOM)로 확인되며, `주요 유료관광지점 입장객 수_내국인 .csv`처럼 공백이 포함된 파일명도 존재하므로 로딩 시 주의가 필요합니다.

## 2. 전처리 목표와 전체 파이프라인

- 통합 기준 시계열 축(월 단위)을 마련해 모든 데이터소스를 정렬.
- 위치·카테고리·고객군 등 공통 차원을 정의하여 패널 형태로 결합.
- 결측/이상치를 체계적으로 처리하고, 성장률·계절성·추세 등 파생 피처 생성.
- 딥러닝 입력을 위해 정규화/스케일링·시퀀스 윈도잉·학습/검증/테스트 분할까지 일괄 수행.

## 3. 공통 전처리 규칙

- **인코딩 및 컬럼명**: `pd.read_csv(..., encoding="utf-8-sig")`로 통일하고, 컬럼명을 `snake_case`로 정리(예: `기준년월` → `base_ym`). 공백/특수문자는 `_`로 치환.
- **날짜 파싱**: 아래 패턴을 모두 `pd.to_datetime`으로 변환 후 `month` 레벨로 정렬.
  - `기준월`, `기준년월`, `기간`, `발행년월`, `SCCNT_DE`, `EXAMIN_BEGIN_DE`, `EXAMIN_YM`, `기준연월`.
  - `연도+월` 조합(`월별_*` 시리즈)은 `year*100 + month` 형태로 결합.
- **식별자 표준화**: 시도/시군구/행정동/관광지명 등은 별도 마스터 테이블을 만들어 표준 명칭·코드를 부여(중복·동의어 방지).
- **결측 관리**: `analysis_summary.json`의 `missing_rate_top`을 참조해
  - 전월/전년 보간이 의미 있는 지표 → `ffill`, `rolling().mean()`, `interpolate(method="time")`.
  - 비율/지수형 → 최소한의 클리핑 후 0 또는 중앙값 대체.
  - 설문 응답 → 가중평균 계산 시 응답 비율(`RSPNS_RATE`) 기반 재계산.
- **중복·이상치**: 동일 월·카테고리 중복행은 합계 또는 평균으로 축약. 극단값은 `z-score` 또는 `IQR`로 검출 후 도메인 확인.

## 4. 데이터 유형별 전처리 전략

### 4.1 월별 집계 시계열 (`월별_*`, `내외국인_관광소비 추이`, `월별_파주시방문 추이`, `월별_경기도_파주시_지역화폐 발행및이용현황`)
- **시계열 정렬**: 모든 데이터프레임을 `datetime` 컬럼 하나(`target_month`)로 통합하고, 지역/카테고리 키(`region_id`, `category_id`)를 추가.
- **패널 리샘플링**: 각 `(region_id, category_id)` 별로 `pd.date_range`를 생성해 누락 월을 채운 뒤, 결측값은 시계열 보간.
- **파생 피처**:
  - 이동평균/이동표준편차 (`window=[3,6,12]`).
  - 증감률 (`pct_change(periods=[1,3,12])`).
  - 계절성 인코딩 (`sin/cos` of month, 분기 더미).
  - 경기/성수기 구분(`성수기 구분`)은 원-핫 + 가중치 적용.
- **정규화**: 값의 규모가 큰 `매출금액(백만원)`, `방문인구(명)` 등은 로그 변환 후 `StandardScaler` 혹은 `RobustScaler`.

### 4.2 설문 기반 시계열 (`설문_국내_*`, `설문_국내여행_TOP10_트랜드_데이터_결과`)
- **코드 매핑**: `*_FLAG_CD`, `RESPOND_CHARTR_SDIV_ID` 등 코드를 `columns_mean_json_en/ko`를 참고해 의미 있는 라벨로 변환.
- **가중 집계**: 응답 비율(`RSPNS_RATE`) 또는 표본수 컬럼을 사용해 월별·인구통계별 가중평균을 계산.
- **희소 행렬 처리**: 관심도/비용 의향 데이터는 `pivot_table(index="target_month", columns=[demographic keys], values=value)` 후
  - 희소성 높은 경우 `TruncatedSVD`, `AutoEncoder`로 차원 축소.
  - 또는 임베딩 입력 대비를 위해 `LabelEncoder`→`Embedding`.
- **시간 정합**: 설문 수집 시작일(`EXAMIN_BEGIN_DE`)을 해당 월 첫날로 정규화해 다른 월별 지표와 정렬.

### 4.3 순위·랭킹 데이터 (`인기관광지_*`, `지역_*`, `중심 관광지`, `주요 유료관광지점 입장객 수_*`)
- **정적 vs 동적 구분**: 월 정보가 있는 `주요 유료관광지점 입장객 수_*`는 시계열로 편성, 나머지 Top-N 리스트는 최신 스냅샷으로 취급.
- **특성 생성**:
  - 순위 → `1/rank`, `top_n_flag`.
  - 관광지/맛집 ID는 위치 마스터와 조인해 지역별 누적 가중치(예: 상위 10개 점수 합) 생성.
  - 방문객 수는 월 단위로 재집계해 주 시계열 테이블에 합산.

### 4.4 정적 스냅샷 (`현시점_*`, `년도별_인구감소지역 현황*`)
- **스칼라 피처화**: 행정동 단위 지표를 표준화 후 동일 지역의 모든 월에 조인(정적 외생 변수).
- **범주형 처리**: 업종/소비규모군 등은 `OneHotEncoder` 또는 사전 정의된 임베딩으로 변환.
- **시간 레이블링**: 최신 연·월을 별도 컬럼(`snapshot_month`)으로 남겨 시점 갱신 시 추적 가능하도록.

## 5. 특성 엔지니어링 및 스케일링

- **ラ그/리드**: `lag_k` (1,3,6,12), `lead_k` (예측 대상 월) 생성.
- **누적 지표**: `cumsum`을 이용해 연초 누적, 최근 12개월 누적 등을 구성.
- **상대 비율**: 동일 월 내 카테고리 대비 비율, 지역 점유율 등 정규화된 피처 추가.
- **스케일링 전략**:
  - 전역 스케일러(Standard/Robust) + `sklearn.preprocessing` `Pipeline`.
  - 순위·비율형은 0~1 스케일 유지, 로그 변환은 양수 값에 한정.
- **변수 그룹화**: 피처 사전을 만들어 (수요, 공급, 관광인프라, 소비, 설문) 그룹별 스케일러 관리 → 모델 해석 용이.

## 6. 학습 데이터셋 구성

1. **마스터 시계열 테이블 구축**  
   - 키: `target_month`, `region_id`, `category_id` (필요 시 `tourist_type`, `demographic` 등 추가).
   - 값: 합쳐진 모든 수치·카테고리 피처.
2. **윈도잉**  
   - 예: 입력 12개월 + 예측 1~3개월.  
   - `SlidingWindowDataset` 형태로 배열화(`TensorDataset` 또는 `tf.data.Dataset`).
3. **데이터 분할**  
   - 시간 기준: `train <= 2024`, `valid = 2025-01~2025-03`, `test >= 2025-04` 등.  
   - 지역/카테고리별로 최소 샘플 개수를 보장하도록 가중 샘플링.
4. **배치 생성**  
   - 딥러닝 모델별 요구 사항(LSTM/Transformer/Temporal Fusion Transformer)에 맞춰 `mask`·`static covariate` 등 준비.

```python
import pandas as pd
from sklearn.preprocessing import StandardScaler

df = pd.read_csv("data_csv_type/월별_관광지_방문객추세_LG유플러스.csv",
                 encoding="utf-8-sig")
df["target_month"] = pd.to_datetime(df["기준월"])
df = df.sort_values(["target_month"])
df.set_index(["target_month"], inplace=True)

features = df[["방문인구(명)", "전월대비 증감률(%)"]].ffill()
scaler = StandardScaler()
scaled = scaler.fit_transform(features)

sequence_length = 12
X, y = [], []
for i in range(len(scaled) - sequence_length):
    X.append(scaled[i:i+sequence_length])
    y.append(scaled[i+sequence_length, 0])  # 방문인구 예측
```

## 7. 품질 검증 및 산출

- **데이터 밸리데이션**: 결측 비율, 이상치 검정 결과를 `Great Expectations` 또는 자체 스크립트로 리포팅.
- **시각 점검**: 주요 지표(방문인구, 매출, 검색량)의 원본 vs 전처리 결과를 라인 차트로 비교.
- **버전 관리**: 가공 산출물은 `processed/<yyyymmdd>/` 구조로 저장하고, 사용한 파이프라인 설정(YAML)과 함께 커밋.
- **재현성 확보**: `pyproject.toml` 혹은 `requirements.txt`로 의존성 고정, 파이프라인은 Notebook보다 스크립트/CLI화 권장.

---

위 절차를 따르면 여러 소스의 월별 데이터가 하나의 시계열 패널로 정리되어 LSTM, Temporal Fusion Transformer, N-BEATS 등 딥러닝 모델에 바로 투입할 수 있는 입력 구조를 확보할 수 있습니다. 필요 시 `progress_notes_step2.md`의 업무 기록과 연동해 세부 우선순위를 조정하세요.
