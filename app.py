from flask import Flask

app = Flask(__name__)
app.secret_key = "your-secret-key-change-this-later"

@app.route('/')
def hello():
    return "It works!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
