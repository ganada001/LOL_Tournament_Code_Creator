# 개인정보 처리방침

최종 수정일: 2026년 6월 23일

LOL Tournament Code Creator는 League of Legends 커뮤니티 대회 운영자를 위한
토너먼트 코드 발급 도구입니다.

## 수집하거나 사용하는 정보

- 운영자 로그인을 위한 이메일과 인증 세션 정보
- 운영자가 직접 등록한 Discord 웹훅 URL
- 로컬에 저장되는 대회 프리셋 이름, 경기 설정, 전송 대상 정보

본 도구는 Riot 계정 정보, Riot 비밀번호, 플레이어 개인정보, Riot API 키를
사용자에게 요구하지 않습니다.

## Riot API 키 처리

Riot API 키는 데스크톱 앱에 저장하지 않습니다. 승인 전 Development API key와
승인 후 Production API key는 보안 백엔드 secret으로만 관리하며, 앱은 인증된
작업 요청만 백엔드로 보냅니다.

## 콜백 URL 처리

Riot 콜백 URL은 서버 secret인 `RIOT_CALLBACK_URL`로 관리합니다. 데스크톱 앱
설정 화면에서 사용자가 직접 입력하는 값이 아닙니다. live Tournament API 코드
발급 시에는 서버가 metadata를 서명하고, public callback endpoint는
`RIOT_CALLBACK_SECRET`으로 서명을 검증합니다.

## 로컬 저장

운영자 세션과 프리셋은 운영자 기기의 로컬 앱 데이터 폴더에 저장됩니다. 로컬
설정, 환경 파일, 캐시, 빌드 산출물은 공개 배포물에 포함하지 않습니다.

## 외부 서비스

- Supabase: 운영자 인증과 서버 측 Edge Function 실행에 사용합니다.
- Riot Games API: Tournament API 작업에 사용합니다.
- Discord Webhook: 운영자가 설정한 경우에만 코드 전달에 사용합니다.

## 문의

보안 또는 개인정보 관련 문의는 GitHub 저장소의 이슈를 통해 남길 수 있습니다.
