from flask import Flask, request
from flask_socketio import SocketIO
import json

app = Flask(__name__)

app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*") #跨域问题
@socketio.on('connect')
def test_connect():
    print('Client connected')

@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected')

@app.route('/', methods=['POST','GET'])
def testttt():
    return "success"

@app.route('/send_msg', methods=['POST'])
def send_msg():
    if request.method == 'POST':
        postdata = request.get_data(as_text=True)
        query_data = json.loads(postdata)
        if "target" in query_data.keys() and "msg" in query_data.keys():
            if type(query_data["msg"]) == str:
                socketio.emit(str(query_data["target"]), str(query_data["msg"]))
            else:
                socketio.emit(str(query_data["target"]), json.dumps(query_data["msg"]))
            return "success"
        else:
            return "failed"
    else:
        return "failed"

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,session_id')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS,HEAD')
    # 这里不能使用add方法，否则会出现 The 'Access-Control-Allow-Origin' header contains multiple values 的问题
    response.headers['Access-Control-Allow-Origin'] = '*'
    #response.headers.add('Access-Control-Allow-Credentials', 'true')
    # response.headers['Access-Control-Allow-Origin'] = 'http://localhost:8080'
    return response


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8081, allow_unsafe_werkzeug=True)
