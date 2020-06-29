from flask import Flask, request, redirect, url_for, render_template, session
from flask_socketio import SocketIO, join_room
from flask_restful import Resource, Api
from flask_bcrypt import Bcrypt
from bson.objectid import ObjectId
import time
import uuid
import json

from db import mongo
import settings


app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
app.config['MONGO_DBNAME'] = 'Users'
app.config['MONGO_URI'] = settings.MONGO_URI

api = Api(app)
bcrypt = Bcrypt(app)

socketio = SocketIO(app)
socketio.init_app(app, cors_allowed_origins="*")

QUERY_ASSIGN_BUFFER = 3
message_queue = []
query_map = {}
ROOM = 'legal_broadcast_room'

@app.route('/')
def index():
    return render_template('loginpage.html')

@app.route('/register_legal', methods=['POST'])
def register_legal():
    data = request.form
    print(data)
    db_response = ''
    payload = {
        'username': data['username'],
        'email': data['email'],
        'password': data['password'],
        'reporting_users': [],
    }
    user_collection = mongo.Users.Legal_team
    flag = user_collection.find_one({
        'email': data['email'],
    })
    if flag == None:
        db_response = user_collection.insert(payload)
        print(db_response)
    else:
        db_response = flag['_id']
    return redirect(url_for('auth'))

@app.route('/delete_legal/<legal_id>')
def delete_legal(legal_id):
    user_collection = mongo.Users.Legal_team
    user_collection.delete_one({
        '_id': ObjectId(legal_id)
    })
    return redirect(url_for('auth'))

@app.route('/login' , methods=['GET' , 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['roomid']
        email = request.form['email']
        if email=="admin" and password=="admin":
            session['username'] = "superadmin"
            session['id'] = email
            print(email)
            return redirect(url_for('auth'))
        else:
            return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/dashboard')
def auth():
    if session.get('id') and session.get('username'):
        public_users = fetch_public_users()
        legal_users = fetch_legal_users()
        return render_template('dashboard.html', users_data={
            'public': public_users,
            'legal': legal_users,
            'lea': [],
        })
    else:
        return redirect(url_for('index'))

@app.route('/manage_tickets')
def manage_tickets():
    payload = []
    ticket_collection = mongo.Queries.Query_tickets
    public_user_collection = mongo.Users.Public
    legal_users_collection = mongo.Users.Legal_team
    messages_collection = mongo.Messages.messages

    tickets = ticket_collection.find()

    for ticket in tickets:
        messages = messages_collection.find({
            'ticket_id': str(ticket['_id']),
        })
        
        p_user = public_user_collection.find_one({
                    'uid': ticket['user_id'],
                })['username']
        l_user = legal_users_collection.find_one({
                    '_id': ticket['legal_assigned'],
                })['username']

        temp1 = {
            'ticket_id': str(ticket['_id']),
            'username': p_user,
            'legal': l_user,
            'status': ticket['status'],
            'messages': [],
        }
        for message in messages:
            temp = {}
            temp['type'] = message['type']
            temp['msg'] = message['msg']
            temp['timestamp'] = message['timestamp']
            temp1['messages'].append(temp)
        payload.append(temp1)
    return render_template("manage_tickets.html", payload=payload)



class RegisterUserApi(Resource):
    def post(self):
        data = request.get_json()
        db_response = ''
        payload = {
            'uid': data['uid'],
            'username': data['username'],
            'email': data['email'],
            'photoUrl': data['photoUrl'],
        }
        user_collection = mongo.Users.Public
        flag = user_collection.find_one({
            'uid': data['uid'],
        })
        if flag == None:
            db_response = user_collection.insert(payload)
            print(db_response)
        else:
            db_response = flag['_id']
        return {'username': payload['username'], 'id': str(db_response)
        }, 201

class AuthenticateUserApi(Resource):
    def post(self, user_type):
        print(user_type)
        data = request.get_json()
        user_collection = mongo.Users.Public if user_type == 'public' else mongo.Users.Legal_team
        db_response = user_collection.find_one({
            'email': data['email']
        })
        print(db_response)
        if db_response:
            if user_type=='public' and bcrypt.check_password_hash(db_response['password'], data['password']):        
                return {
                    'username': db_response['username'], 'id': str(db_response['_id'])
                }, 201
            if db_response['password'] == data['password']:
                legals = list(mongo.Users.Legal_team.find({}))
                legals_data = []
                for legal in legals:
                    if str(legal['_id']) != str(db_response['_id']):
                        l = {}
                        l['id'] = str(legal['_id'])
                        l['name'] = legal['username']
                        l['email'] = legal['email']
                        legals_data.append(l)
                return {
                    'username': db_response['username'],
                    'id': str(db_response['_id']),
                    'legals_data': legals_data,
                }, 201
        return {}, 401

class TicketHandlerApi(Resource):
    def post(self):
        data = request.get_json()
        ticket_details = mongo.Queries.Query_tickets.find_one({
            '_id': ObjectId(data['ticket_id'])
        })

        if ticket_details:
            legal_username = mongo.Users.Legal_team.find_one({
                '_id': ticket_details['legal_assigned']
            })['username']
            user_details = mongo.Users.Public.find_one({
                'uid': ticket_details['user_id']
            })
            return {
                'legal_username': legal_username,
                'user_id': ticket_details['user_id'],
                'legal_id': str(ticket_details['legal_assigned']),
                'user_email': user_details['email'],
                'user_name': user_details['username'],
                'photoUrl': user_details['photoUrl']
            }, 201
        else:
            return {} , 401


class LegalMessageRetrievalApi(Resource):
    def post(self):
        data = request.get_json()
        res = legal_message_history_retrieval(data['legal_id'])
        return {
            'data': res,
        }, 201

class CallRequestsRetrievalApi(Resource):
    def post(self):
        data = request.get_json()
        res = legal_call_requests_retrieval(data['legal_id'])
        return {
            'data': res,
        }, 201

class UpdateUserApi(Resource):
    def post(self):
        data = request.get_json()
        user_collection = mongo.Users.Public
        user_collection.update_one({
            "uid": data["uid"],
        }, {
            "$set": data
        })
        

api.add_resource(RegisterUserApi, '/register_user')
api.add_resource(UpdateUserApi, '/update_user')
api.add_resource(AuthenticateUserApi, '/authenticate_user/<user_type>')
api.add_resource(TicketHandlerApi , '/ticket_handler')
api.add_resource(LegalMessageRetrievalApi , '/retrieve_legal_messages')
api.add_resource(CallRequestsRetrievalApi , '/retrieve_call_requests')


def legal_call_requests_retrieval(legal_id):
    payload = []
    call_tickets = mongo.Queries.Callback
    legal_collection = mongo.Users.Legal_team

    call_queue = legal_collection.find_one({
        '_id': ObjectId(legal_id)
    })["call_queue"]

    for ticket in call_queue:
        temp = call_tickets.find_one({
            '_id': ticket,
        })
        temp['_id'] = str(temp['_id'])
        temp['legal_assigned'] = str(temp['legal_assigned'])
        payload.append(temp)
    return payload


def legal_message_history_retrieval(legal_id):
    payload = []
    ticket_collection = mongo.Queries.Query_tickets
    public_user_collection = mongo.Users.Public
    messages_collection = mongo.Messages.messages

    tickets = ticket_collection.find({
        'legal_assigned': ObjectId(legal_id),
    })

    for ticket in tickets:
        messages = messages_collection.find({
            'ticket_id': str(ticket['_id']),
        })
        
        p_user = public_user_collection.find_one({
                    'uid': ticket['user_id'],
                })['username']

        temp1 = {
            'ticket_id': str(ticket['_id']),
            'username': p_user,
            'messages': [],
        }
        for message in messages:
            temp = {}
            temp['type'] = message['type']
            temp['msg'] = message['msg']
            temp['timestamp'] = message['timestamp']
            temp1['messages'].append(temp)
        payload.append(temp1)
    return payload


def fetch_public_users():
    public_users_collection = mongo.Users.Public
    payload = []
    for user in public_users_collection.find():
        user['_id'] = str(user['_id'])
        payload.append(user)
    return payload

def fetch_legal_users():
    legal_users_collection = mongo.Users.Legal_team
    payload = []
    for user in legal_users_collection.find():
        user['_id'] = str(user['_id'])
        payload.append(user)
    return payload


def call_query_assignment():
    min_t = 4
    idx = ''
    rep_users = []
    legals_cursor = mongo.Users.Legal_team.find()
    for legal in legals_cursor:
        l = len(legal['call_queue'])
        if l <= min_t:
            min_t = l
            idx = legal['_id']
            rep_users = legal['call_queue']
    rep_users = list(map(lambda user: str(user) , rep_users))
    return idx , rep_users

def query_assignment():
    min_t = 4
    idx = ''
    rep_users = []
    legals_cursor = mongo.Users.Legal_team.find()
    for legal in legals_cursor:
        l = len(legal['reporting_users'])
        if l <= min_t:
            min_t = l
            idx = legal['_id']
            rep_users = legal['reporting_users']
    rep_users = list(map(lambda user: str(user) , rep_users))
    return idx , rep_users

def find_legals_by_sid(sid):
    for i in range(len(legals)):
        if legals[i]['sid'] == sid:
            return i


def fetch_user_details(users):
    rep_users = []
    for user in users:
        user_id = mongo.Queries.Query_tickets.find_one({
            '_id': user,
        })
        user_data = mongo.Users.Public.find_one({
            'uid': user_id['user_id'],
        })
        user_data['_id'] = str(user_data['_id'])
        user_data['ticket_id'] = str(user)
        user_data['bot_conv'] = mongo.Messages.bot_messages.find_one({
            '_id': ObjectId(user_id['bot_session_id']),
        })['conversation']
        rep_users.append(user_data)
    return rep_users

def retrieve_message_list(user_id):
    payload = []

    ticket_collection = mongo.Queries.Query_tickets
    public_user_collection = mongo.Users.Public
    legal_user_collection = mongo.Users.Legal_team
    messages_collection = mongo.Messages.messages
    bot_message_collection = mongo.Messages.bot_messages

    bot_messages_iter = bot_message_collection.find({
        'user_id': user_id,
    })

    for bot_message in bot_messages_iter:
        for conversation in bot_message['conversation']:
            payload.append(conversation)

    tickets = ticket_collection.find({
        'user_id': user_id,
    })

    for ticket in tickets:
        messages = messages_collection.find({
            'ticket_id': str(ticket['_id']),
        })
        for message in messages:
            temp = {}
            temp['ticket_id'] = str(ticket['_id'])
            legal_id = ticket['legal_assigned']
            temp['type'] = message['type']
            temp['msg'] = message['msg']
            temp['timestamp'] = message['timestamp']
            if message['type'] == 'user_id':
                user = public_user_collection.find_one({
                    'uid': user_id,
                })['username']
                temp['id'] = user_id
                temp['username'] = user
            else:
                user = legal_user_collection.find_one({
                    '_id': legal_id,
                })['username']
                temp['id'] = str(legal_id)
                temp['username'] = user
            payload.append(temp)
    
    return payload
            

@socketio.on('push_to_db')
def push_to_db(data):
    if type(data) is unicode:
        data = json.loads(data)
    mongo.Messages.bot_messages.update_one({
        '_id': ObjectId(data['bot_id']),
    }, {
        '$push': {
            'conversation': data['msg'],
        }
    })

@socketio.on('retrieve_data')
def socket_retrieve_from_db(data):
    if type(data) is unicode:
        data = json.loads(data)
    bot_message = data['message']
    bot_session_id = mongo.Messages.bot_messages.insert({
        'user_id': bot_message['user_id'],
        'conversation': [bot_message],
    })
    message_list = retrieve_message_list(data['room'])
    join_room(data['room'])
    socketio.emit('join_room_bot', {
        'bot_session_id': str(bot_session_id),
        'message_list': message_list,
    }, room=data['room'])


@socketio.on('request_callback')
def request_callback_handler(data):
    print(type(data))
    if type(data) is unicode:
        data = json.loads(data)
    # app.logger.info(retrieve_message_list(data['room']))
    query_queue = mongo.Queries.Callback
    flag = query_queue.find_one({
        'user_id': data['id'],
	'status': 'open',
    })
    legal_idx = ''
    queue_id = ''
    rep_users = []
    if flag != None :
        legal_idx = flag['legal_assigned']
        queue_id = flag['_id']
        users_t = mongo.Users.Legal_team.find_one({
            '_id': legal_idx
        })['call_queue']
        rep_users = users_t
        
    else:
        legal_idx , rep_users = call_query_assignment()
        queue_id = query_queue.insert({
            'user_id': data['id'],
            'u_sid': request.sid,
            'legal_assigned': legal_idx,
            'status': 'open',
            'number': data['number'],
            'username': data['name'],
            'type': 'public', #make dynamic with adding type data to request header
            'report': False,
        })
        rep_users.append(queue_id)
        mongo.Users.Legal_team.update_one({
            '_id': legal_idx
        }, {
            '$push': {
                'call_queue': queue_id
            }
        })

@socketio.on('join_room')
def join_room_handler(data):
    print(type(data))
    if type(data) is unicode:
        data = json.loads(data)
    # app.logger.info(retrieve_message_list(data['room']))
    query_queue = mongo.Queries.Query_tickets
    flag = query_queue.find_one({
        'user_id': data['room'],
	'status': 'open',
    })
    legal_idx = ''
    queue_id = ''
    rep_users = []
    if flag != None :
        legal_idx = flag['legal_assigned']
        queue_id = flag['_id']
        users_t = mongo.Users.Legal_team.find_one({
            '_id': legal_idx
        })['reporting_users']
        rep_users = users_t
        
    else:
        legal_idx , rep_users = query_assignment()
        queue_id = query_queue.insert({
            'user_id': data['room'],
            'u_sid': request.sid,
            'legal_assigned': legal_idx,
            'status': 'open',
            'bot_session_id': data['bot_id'],
            'tags': [],
            'type': 'public', #make dynamic with adding type data to request header
            'report': False,
        })
        rep_users.append(queue_id)
        mongo.Users.Legal_team.update_one({
            '_id': legal_idx
        }, {
            '$push': {
                'reporting_users': queue_id
            }
        })
    rep_users = fetch_user_details(rep_users)
    join_room(data['room'])
    join_room((data['room'] + str(legal_idx)))
    print('Client - ' + data['room'] + str(legal_idx))
    socketio.emit('join_room_ack', {
        'legal_id': str(legal_idx),
        'ticket_id': str(queue_id),
    }, room=data['room'])
    socketio.emit('new_join_legal_ack' , rep_users , room=str(legal_idx))

@socketio.on('pass_query_legal')
def pass_legal(data):
    print(data)
    legal_collection = mongo.Users.Legal_team
    legal_collection.update_one({
        '_id': ObjectId(data['from'])
    }, {
        '$pull': {
            'reporting_users': ObjectId(data['ticket_id'])
        }
    })
    legal_collection.update_one({
        '_id': ObjectId(data['to'])
    }, {
        '$push': {
            'reporting_users': ObjectId(data['ticket_id'])
        }
    })
    from_legal = legal_collection.find_one({
        '_id': ObjectId(data['from'])
    })['reporting_users']
    to_legal = legal_collection.find_one({
        '_id': ObjectId(data['to'])
    })['reporting_users']
    socketio.emit('new_join_legal_ack', fetch_user_details(from_legal), room=data['from'])
    socketio.emit('new_join_legal_ack' , fetch_user_details(to_legal) , room=data['to'])


@socketio.on('chats')
def chat_handler(data):
    if type(data) is unicode:
        data = json.loads(data)
    payload = {
        'username': data['username'],
        'id': data[data["type"]],
        'msg': data['msg'],
        'type': data['type'],
        'ticket_id': data['ticket_id'],
        'timestamp': data['timestamp'],
    }
    db_payload = {
        'type': data['type'],
        'msg': data['msg'],
        'timestamp': data['timestamp'],
        'ticket_id': data['ticket_id'],
    }
    mongo.Messages.messages.insert_one(db_payload)
    print(db_payload)
    socketio.emit('messaging_handle', payload, room=(data["user_id"] + data["legal_id"]))


@socketio.on('join_legal_room')
def legal_room_handler(data):
    app.logger.info("legal:" + data['username'] + " " + data['room'])
    users_t = mongo.Users.Legal_team.find_one({
        '_id': ObjectId(data['room'])
    })['reporting_users']
    users_t = fetch_user_details(users_t)
    join_room(ROOM)
    join_room(data['room'])
    socketio.emit('join_legal_room_ack', data, room=ROOM)
    socketio.emit('new_join_legal_ack' , users_t , room=data['room'])


@socketio.on('close_ticket')
def ticket_close(ticket_data):
    print(ticket_data)
    ticket_cursor = mongo.Queries.Query_tickets.find_one({
        '_id': ObjectId(ticket_data['ticket_id'])
    })
    users_t = []
    legal_idx = ''
    if ticket_cursor:
        users_t, legal_idx = ticket_deletion(ticket_cursor)
        print(users_t)
    socketio.emit('new_join_legal_ack' , fetch_user_details(users_t) , room=legal_idx)

def ticket_deletion(ticket_cursor):
    legal_idx = ticket_cursor['legal_assigned']
    ticket_id = ticket_cursor['_id']

    mongo.Users.Legal_team.update_one({
        '_id': legal_idx
    }, {
        '$pull': {
            'reporting_users': ticket_id
        }
    })

    mongo.Queries.Query_tickets.update_one({
        '_id': ticket_id
    }, {
        '$set': {
            'status': 'closed'
        }
    })
    users_t = mongo.Users.Legal_team.find_one({
        '_id': legal_idx
    })['reporting_users']
    return fetch_user_details(users_t), str(legal_idx)
    

@socketio.on('messaging_handle_join')
def messaging_handle_join(data):
    broadcast_message = data['username'] + ' is here to help you.'
    join_room((data['user_id'] + data['legal_id']))
    print('Legal -- ' + data['user_id'] + data['legal_id'])
    payload = {
        'username': data['username'],
        'id': data[data["type"]],
        'msg': broadcast_message,
        'type': data['type'],
        'ticket_id': data['ticket_id'],
        'timestamp': data['timestamp'],
    }
    db_payload = {
        'type': data['type'],
        'msg': broadcast_message,
        'ticket_id': data['ticket_id'],
        'timestamp': data['timestamp'],
    }
    mongo.Messages.messages.insert_one(db_payload)
    socketio.emit('messaging_handle', payload, room=(data['user_id'] + data['legal_id']))


if __name__ == '__main__':
    socketio.run(app, port=3010, debug=True)
