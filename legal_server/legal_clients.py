from flask import Flask , render_template , request , redirect , url_for , session
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = 'randomsecretkey'

legal_id = ''
legal_username = ''

@app.route('/')
def index():
    return render_template('loginpage.html')

@app.route('/login' , methods=['GET' , 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['roomid']
        email = request.form['email']
        res = requests.post('https://cyaid.hackdevtechnology.com/authenticate_user/legal', json={
            'password': password,
            'email': email
        })
        if res.status_code == 201:
            res = res.json()
            session['username'] = res['username']
            session['id'] = res['id']
            session['legals_data'] = res['legals_data']
            print(res['legals_data'])
            return redirect(url_for('auth'))
        else:
            return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/chat_bubble')
def chat_bubble():
    return render_template('chat_bubble.html')


@app.route('/dashboard')
def auth():
    if session.get('id') and session.get('username'):
        return render_template('dashboard.html', user_cred={
            'name': session['username'],
            'room': session['id'],
            'legals_data': session['legals_data']})
    else:
        return redirect(url_for('index'))

@app.route('/history')
def history():
    if session.get('id') and session.get('username'):
        res = requests.post('https://cyaid.hackdevtechnology.com/retrieve_legal_messages', json={
            'legal_id': session.get('id'),
        })
        return render_template('history.html', user_cred={
            'name': session['username'],
            'room': session['id'],
            'legals_data': session['legals_data'],
            'message_data': res.json()['data'],
        })
    else:
        return redirect(url_for('index'))

@app.route('/call_requests')
def call_requests():
    if session.get('id') and session.get('username'):
        res = requests.post('https://cyaid.hackdevtechnology.com/retrieve_call_requests', json={
            'legal_id': session.get('id'),
        })
        print(res.json())
        return render_template('call_requests.html', user_cred={
            'name': session['username'],
            'room': session['id'],
            'legals_data': session['legals_data'],
            'call_requests': res.json()['data']
        })
    else:
        return redirect(url_for('index'))

@app.route('/chat_handler/<ticket_id>', methods=['GET', 'POST'])
def chat_handler(ticket_id):
    res = requests.post('https://cyaid.hackdevtechnology.com/ticket_handler', json={
        'ticket_id': ticket_id
    })
    if res.status_code == 201:
        res = res.json()
        print(res)
        return render_template('chat_screen.html', ticket_cred={
            'user_id': res['user_id'],
            'legal_id': res['legal_id'],
            'username': res['legal_username'],
            'p_username': res['user_name'],
            'user_email': res['user_email'],
            'ticket_id': ticket_id,
        })
    else:
        return "<h1>Error</h1>"

if __name__ == "__main__":
    app.run(debug=True, port=3009)
