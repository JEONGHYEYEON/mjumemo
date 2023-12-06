from http import HTTPStatus
import random
import requests
import json
import urllib
from pymongo import MongoClient
from flask import abort, Flask, make_response, render_template, Response, redirect, request, jsonify


# --------------------------------------- mongoDB : memo 연결----------------------------------------------------------#
app = Flask(__name__)
client = MongoClient("mongodb://localhost:27017/hyeyeon?retryWrites=true&w=majority")
app.config['MONGO_URI'] = 'mongodb://localhost:27017/hyeyeon?retryWrites=true&w=majority' 
client = MongoClient(app.config['MONGO_URI'])
db = client.mjubackend
app.config.from_object(__name__)

User = db['user'] # 유저 정보를 저장하는 컬렉션
Memo = db['memo'] # 유저의 메모를 저장하는 컬렉션 
# --------------------------------------------------------------------------------------------------------------------#

naver_client_id = 'I7WfwPKXWPVPPQi78Ifp'
naver_client_secret = 'WMcnl8KY7S'
naver_redirect_uri = 'http://localhost:8000/auth'


@app.route('/')
def home():
    userId = request.cookies.get('userId', default=None)
    name = None

    if userId:
        user = User.find_one({'user_id': userId})
        if user:
            name = user['user_name']

    return render_template('index.html', name=name)


# 로그인 버튼을 누른 경우 이 API 를 호출한다.
# OAuth flow 상 브라우저에서 해당 URL 을 바로 호출할 수도 있으나,
# 브라우저가 CORS (Cross-origin Resource Sharing) 제약 때문에 HTML 을 받아온 서버가 아닌 곳에
# HTTP request 를 보낼 수 없는 경우가 있다. (예: 크롬 브라우저)
# 이를 우회하기 위해서 브라우저가 호출할 URL 을 HTML 에 하드코딩하지 않고,
# 아래처럼 서버가 주는 URL 로 redirect 하는 것으로 처리한다.
#
# 주의! 아래 API 는 잘 동작하기 때문에 손대지 말 것
@app.route('/login')
def onLogin():
    params={
            'response_type': 'code',
            'client_id': naver_client_id,
            'redirect_uri': naver_redirect_uri,
            'state': random.randint(0, 10000)
        }
    urlencoded = urllib.parse.urlencode(params)
    url = f'https://nid.naver.com/oauth2.0/authorize?{urlencoded}'
    return redirect(url)


@app.route('/auth')
def onOAuthAuthorizationCodeRedirected():
    # 1. 코드 및 상태 획득
    code = request.args.get('code')
    state = request.args.get('state')

    # 2. Access token 획득
    token_request_payload = {
        'grant_type': 'authorization_code',
        'client_id': naver_client_id,
        'client_secret': naver_client_secret,
        'redirect_uri': naver_redirect_uri,
        'code': code,
        'state': state
    }
    token_response = requests.post('https://nid.naver.com/oauth2.0/token', data=token_request_payload)
    access_token = token_response.json().get('access_token')

    # 3. 프로필 정보 획득
    headers = {'Authorization': f"Bearer {access_token}"}
    profile_response = requests.get('https://openapi.naver.com/v1/nid/me', headers=headers)
    user_info = profile_response.json().get('response')
    user_id = user_info.get('id')
    user_name = user_info.get('name')

    # 4. DB에 저장
    User.update_one({'user_id': user_id}, {'$set': {'user_name': user_name}}, upsert=True)

    # 5. 리디렉트 및 쿠키 설정
    response = redirect('/')
    response.set_cookie('userId', user_id)
    return response


@app.route('/memo', methods=['GET'])
def get_memos():
    userId = request.cookies.get('userId', default=None)
    if not userId:
        return jsonify({'error': 'User not logged in'}), 401

    memos = Memo.find({'user_id': userId})
    result = [{'text': memo.get('content', '')} for memo in memos]
    return jsonify({'memos': result})


@app.route('/memo', methods=['POST'])
def post_new_memo():
    
    userId = request.cookies.get('userId', default=None)
    if not userId:
        return redirect('/')
    if not request.is_json:
        abort(HTTPStatus.BAD_REQUEST)

    memo_content = request.json.get('text')
    if memo_content:  # 메모 내용이 비어있지 않은지 검증
        result = Memo.insert_one({"user_id": userId, "content": memo_content})
        print(f"삽입된 문서 ID: {result.inserted_id}")
        return '', HTTPStatus.OK
    else:
        return '메모 내용이 비어있습니다.', HTTPStatus.BAD_REQUEST

@app.route('/health', methods=['GET'])
def health_check():
    return '', HTTPStatus.OK

if __name__ == '__main__':
    app.run('0.0.0.0', port=8000, debug=True)
