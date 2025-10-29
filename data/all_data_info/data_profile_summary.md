# `data_profile_summary.json` 요약

- **역할**: `analysis_summary.json`과 달리 각 CSV 전체 행 수(추정치)까지 포함해 보다 상세한 데이터 프로파일 정보를 제공합니다.
- **구조**: JSON 배열. 항목마다 파일 경로, 인코딩, 전체 행 수(`total_rows_est`), 샘플링 행 수(`sample_rows`), 컬럼 개수(`n_cols`), 컬럼명 배열을 담습니다.
- **사용 팁**
  - 한 파일의 스키마(컬럼 리스트)를 빠르게 확인할 때 활용합니다.
  - `total_rows_est` 값으로 대용량 여부를 가늠하고, `sample_rows`로 실제 확인 가능한 행 수를 참고합니다.
  - 전처리 파이프라인 설계 시 `columns` 배열을 그대로 사용해 컬럼 존재 여부를 검증할 수 있습니다.

> 저장 인코딩은 UTF-8이며, Windows PowerShell에서도 한글 경로가 깨지지 않도록 `ensure_ascii=False`로 직렬화했습니다.
