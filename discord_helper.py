import requests
from urllib.parse import urlparse


DEFAULT_TIMEOUT_SECONDS = 10
DISCORD_EMBED_COLOR = 0x3456A3


def _is_valid_discord_webhook_url(webhook_url):
    parsed = urlparse(webhook_url or "")
    host = parsed.netloc.lower()
    return (
        parsed.scheme == "https"
        and (host == "discord.com" or host.endswith(".discord.com") or host == "discordapp.com")
        and parsed.path.startswith("/api/webhooks/")
    )


def send_discord_webhook(webhook_url, tournament_name, code, timeout=DEFAULT_TIMEOUT_SECONDS):
    if not webhook_url:
        print("오류: 웹훅 URL이 제공되지 않았습니다.")
        return False
    if not _is_valid_discord_webhook_url(webhook_url):
        print("오류: Discord Webhook URL 형식이 올바르지 않습니다.")
        return False

    message = {
        "content": f"**🏆 {tournament_name}**\n토너먼트 코드가 생성되었습니다!",
        "embeds": [
            {
                "title": "롤 토너먼트 생성 완료",
                "description": f"```{code}```\n(롤 클라이언트 -> 플레이 -> 트로피 아이콘 🏆 -> 코드 입력)",
                "color": DISCORD_EMBED_COLOR,
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
        response = requests.post(webhook_url, json=message, timeout=timeout)
        response.raise_for_status()
        return True
    except requests.exceptions.Timeout:
        print(f"웹훅 전송 실패: {timeout}초 내에 응답이 없었습니다.")
        return False
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else "unknown"
        print(f"웹훅 전송 실패: HTTP {status_code}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"웹훅 전송 실패: {e.__class__.__name__}")
        return False
