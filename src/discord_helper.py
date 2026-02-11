import requests
import json

def send_discord_webhook(webhook_url, tournament_name, code):
    """
    생성된 토너먼트 코드를 디스코드 웹훅으로 전송합니다.
    """
    if not webhook_url:
        print("오류: 웹훅 URL이 제공되지 않았습니다.")
        return False

    message = {
        "content": f"**🏆 {tournament_name}**\n토너먼트 코드가 생성되었습니다!",
        "embeds": [
            {
                "title": "롤 토너먼트 생성 완료",
                "description": f"```{code}```\n(롤 클라이언트 -> 플레이 -> 트로피 아이콘 🏆 -> 코드 입력)",
                "color": 3447003, # Blue
                "fields": [
                    {
                        "name": "맵",
                        "value": "소환사의 협곡",
                        "inline": True
                    },
                    {
                        "name": "모드",
                        "value": "토너먼트 드래프트",
                        "inline": True
                    }
                ]
            }
        ]
    }

    try:
        response = requests.post(webhook_url, json=message)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"웹훅 전송 실패: {e}")
        return False
