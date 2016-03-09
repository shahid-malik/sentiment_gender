from flask import Flask, render_template, request, jsonify, make_response
from info import classify2
from math import e
from redis import Redis
from config import STATS_KEY, HOST, RHOST, RPASS, RPORT
from cors import crossdomain
from datetime import datetime
import json
import requests
from hammock import Hammock as GendreAPI

app = Flask(__name__)
app.debug = False
app.config['MAX_CONTENT_LENGTH'] = (1 << 20) # 1 MB max request size
#conn = Redis(RHOST, RPORT, password=RPASS)
sentiment_dict = {'neg': 'Negative', 'pos': 'Positive', 'neutral': 'Neutral'}

def percentage_confidence(conf):
	return 100.0 * e ** conf / (1 + e**conf)

def today():
	return datetime.now().strftime('%Y-%m-%d')

def get_sentiment_info(text):
	#  limited api for 1000 requests/day
	try:
		response = requests.post('http://text-processing.com/api/sentiment/', data={'text': text})
	except requests.exceptions.ConnectionError as e:
		response = False
	print "fakhir2", response
	if response and response.status_code == 200:
		res_dict = json.loads(response.content)
		print res_dict
		try:
			print res_dict['probability']
			print res_dict['probability'][res_dict['label']]
			conf = "%.4f" % percentage_confidence(res_dict['probability'][res_dict['label']])
			sentiment = sentiment_dict[res_dict['label']]
		except Exception, e:
			print e
	else:
		#  If the api do not respond 200, this part will work
		flag, confidence = classify2(text)
		if confidence > 0.5:
			sentiment = "Positive" if flag else "Negative"
		else:
			sentiment = "Neutral"
		conf = "%.4f" % percentage_confidence(confidence)
	return (sentiment, conf)

@app.route('/')
def home():
	#conn.incr(STATS_KEY + "_hits")
	return render_template("index.html")

@app.route('/api/text/', methods=["POST"])
@crossdomain(origin='*')
def read_api():
	text = request.form.get("txt", '')
	sentiment, confidence = get_sentiment_info(text)
	result = {"sentiment": sentiment, "confidence": confidence}
	#conn.incr(STATS_KEY + "_api_calls")
	#conn.incr(STATS_KEY + today())
	print result
	return jsonify(result=result)

@app.route('/web/text/', methods=["POST"])
@crossdomain(origin='*')
def evaldata():
	text = request.form.get("txt")
	result, confidence = get_sentiment_info(text)
	#conn.incr(STATS_KEY + "_web_calls")
	#conn.incr(STATS_KEY + today())
	return jsonify(result=result, confidence=confidence, sentence=text)

@app.route('/api/batch/', methods=["POST"])
@crossdomain(origin='*')
def batch_handler():
	json_data = request.get_json(force=True, silent=True)
	if not json_data:
		return jsonify(error="Bad JSON request")
	result = []
	for req in json_data:
		sent, conf = get_sentiment_info(req)
		result.append({"result": sent, "confidence": conf})

	#conn.incrby(STATS_KEY + "_api_calls", len(json_data))
	#conn.incrby(STATS_KEY + today(), len(json_data))
	resp = make_response(json.dumps(result))
	resp.mimetype = 'application/json'

	return resp

@app.route('/docs/api/')
def api():
	return render_template('api.html', host=HOST)

@app.route('/about/')
def about():
	return render_template('about.html')


@app.route('/api/gender/', methods=["POST"])
@crossdomain(origin='*')
def gender_detection():
	result = {}
	first_name = request.form.get("first_name", '')

	if not first_name:
		result.update({'status': False, 'msg': 'Please provide first_name & last_name these are mandatory!'})
		return jsonify(result=result)
	else:
		names = first_name.split(' ')
		print names, "names"
		for name in names:
			print name
			try:
				gendre = GendreAPI("http://api.namsor.com/onomastics/api/json/gendre")
				resp = gendre(name, 'a').GET()
				print "resp", resp
				gender = resp.json().get('gender', '')
				if gender.lower() == 'male' or gender.lower() == 'female':
					result.update({'status': True, 'gender': gender})
					break
			except Exception, e:
				print str(e)
				result.update({'status': False, 'gender': 'Unknown'})
		return jsonify(result=result)
