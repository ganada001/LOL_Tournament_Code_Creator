// =============================================================
// LOL Tournament Code Creator - GAS Backend Proxy
// =============================================================
// 이 스크립트는 Python 클라이언트의 요청을 받아 Riot API로 전달합니다.
// API Key는 스크립트 속성(Script Properties)에 저장되어 있으므로
// 사용자에게 절대 노출되지 않습니다.
//
// [스크립트 속성 설정법]
// 1. Apps Script 에디터 → 프로젝트 설정(톱니바퀴) → 스크립트 속성
// 2. 속성 이름: RIOT_API_KEY / 값: RGAPI-xxxxx...
// =============================================================

/**
 * POST 요청 핸들러
 * Python api_client.py가 보내는 payload 구조:
 * {
 *   "method": "POST",
 *   "endpoint": "/lol/tournament-stub/v5/providers",  (또는 /tournaments, /codes)
 *   "use_stub": true,
 *   "params": { "count": 1, "tournamentId": 123 },    (선택)
 *   "body": { "region": "KR", "url": "..." }          (선택)
 * }
 */
function doPost(e) {
  try {
    // 1. Python에서 보낸 데이터 파싱
    var requestData = JSON.parse(e.postData.contents);
    
    // 2. 스크립트 속성에서 API 키 가져오기
    var apiKey = PropertiesService.getScriptProperties().getProperty("RIOT_API_KEY");
    if (!apiKey) {
      return jsonResponse({"error": "RIOT_API_KEY not configured in Script Properties"});
    }
    
    // 3. Riot API URL 구성
    var baseUrl = "https://americas.api.riotgames.com";  // Tournament API는 americas 클러스터 사용
    var endpoint = requestData.endpoint || "";
    var riotUrl = baseUrl + endpoint;
    
    // 4. Query Parameters 추가 (예: count, tournamentId)
    if (requestData.params) {
      var queryParts = [];
      for (var key in requestData.params) {
        queryParts.push(encodeURIComponent(key) + "=" + encodeURIComponent(requestData.params[key]));
      }
      if (queryParts.length > 0) {
        riotUrl += "?" + queryParts.join("&");
      }
    }
    
    // 5. Riot API 호출 옵션 설정
    var method = (requestData.method || "POST").toLowerCase();
    var options = {
      "method": method,
      "headers": {
        "X-Riot-Token": apiKey,
        "Content-Type": "application/json"
      },
      "muteHttpExceptions": true
    };
    
    // POST/PUT 등에는 body 추가
    if (requestData.body && (method === "post" || method === "put")) {
      options.payload = JSON.stringify(requestData.body);
    }
    
    // 6. Riot API 호출
    var response = UrlFetchApp.fetch(riotUrl, options);
    var responseCode = response.getResponseCode();
    var responseText = response.getContentText();
    
    // 7. 결과 반환
    // Riot API가 에러를 반환하면 그대로 전달
    if (responseCode >= 400) {
      try {
        var errorData = JSON.parse(responseText);
        return jsonResponse(errorData);
      } catch(parseErr) {
        return jsonResponse({"status": {"status_code": responseCode, "message": responseText}});
      }
    }
    
    // 성공 응답
    try {
      var successData = JSON.parse(responseText);
      return jsonResponse(successData);
    } catch(parseErr) {
      // Riot이 plain text (숫자 등)를 반환할 수도 있음
      return jsonResponse(responseText);
    }
    
  } catch (error) {
    return jsonResponse({"error": error.toString()});
  }
}

/**
 * GET 요청 핸들러 (테스트용)
 */
function doGet(e) {
  return jsonResponse({
    "status": "ok",
    "message": "LOL Tournament Code Creator Backend is running.",
    "timestamp": new Date().toISOString()
  });
}

/**
 * JSON 응답 헬퍼
 */
function jsonResponse(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
