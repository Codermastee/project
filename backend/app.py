from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime
from werkzeug.utils import secure_filename
import os, hashlib, json, requests
from dotenv import load_dotenv

# ------------------- Setup -------------------
load_dotenv()
app = Flask(__name__)
CORS(app)

# MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['qr_database']
patients = db['patients']

# IPFS Pinata
PINATA_API_KEY = os.getenv("PINATA_API_KEY")
PINATA_SECRET_API_KEY = os.getenv("PINATA_SECRET_API_KEY")

# ------------------- IPFS Upload -------------------
def upload_to_ipfs(file_stream, filename):
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    headers = {
        "pinata_api_key": PINATA_API_KEY,
        "pinata_secret_api_key": PINATA_SECRET_API_KEY,
    }
    files = {
        'file': (filename, file_stream)
    }
    response = requests.post(url, files=files, headers=headers)
    if response.status_code == 200:
        ipfs_hash = response.json()["IpfsHash"]
        return f"https://gateway.pinata.cloud/ipfs/{ipfs_hash}"
    else:
        print("IPFS Error:", response.text)
        return None

# ------------------- QR Code APIs -------------------

@app.route('/api/qr', methods=['POST'])
def save_qr_data():
    data = request.get_json()
    if not data or 'id' not in data or 'name' not in data:
        return jsonify({'error': 'Missing patient data'}), 400

    data['timestamp'] = datetime.now().isoformat()
    existing = patients.find_one({'id': data['id']})
    if existing:
        patients.update_one({'id': data['id']}, {'$set': data})
        return jsonify({'message': 'QR data updated'}), 200

    patients.insert_one(data)
    return jsonify({'message': 'QR data stored successfully'}), 201

@app.route('/api/qr', methods=['GET'])
def get_all_qr_data():
    records = list(patients.find({}, {'_id': 0}))
    return jsonify(records), 200

# ------------------- Doctor Verification -------------------

@app.route('/api/doctor/verify', methods=['POST'])
def verify_doctor():
    data = request.get_json()
    valid_doctors = {
        'DR12345': 'access123',
        'DR67890': 'access456',
    }
    if valid_doctors.get(data.get("doctorId")) == data.get("accessCode"):
        return jsonify({'verified': True}), 200
    return jsonify({'verified': False, 'message': 'Invalid credentials'}), 403

# ------------------- Patient APIs -------------------

@app.route('/api/patients/search', methods=['GET'])
def search_patient():
    query = request.args.get('query', '').strip()

    if not query:
        return jsonify({'error': 'Search query required'}), 400

    result = patients.find_one({'id': query})
    
    if not result:
        return jsonify({'error': 'Patient not found'}), 404

    result['_id'] = str(result['_id'])  # Optional for frontend rendering
    return jsonify({'patient': result}), 200

@app.route('/api/patients', methods=['POST'])
def save_patient():
    data = request.get_json()
    if not data.get('id') or not data.get('name'):
        return jsonify({'error': 'Missing patient ID or name'}), 400

    data.pop('_id', None)
    patients.update_one({'id': data['id']}, {'$set': data}, upsert=True)
    return jsonify({'message': 'Patient data saved'}), 200

# ------------------- Add Report (Blockchain-style) -------------------

@app.route('/api/patients/<patient_id>/reports', methods=['POST'])
def add_report(patient_id):
    report = request.form.to_dict()
    file_url = None
    file_hash = None

    # Step 1: File Upload & Hashing
    if 'reportFile' in request.files:
        file = request.files['reportFile']
        filename = secure_filename(file.filename)

        file.stream.seek(0)
        file_bytes = file.stream.read()

        # SHA256 hash
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        report['fileHash'] = file_hash

        # IPFS upload
        file.stream.seek(0)
        file_url = upload_to_ipfs(file.stream, filename)
        if not file_url:
            return jsonify({'error': 'IPFS upload failed'}), 500
        report['fileUrl'] = file_url

    # Step 2: Add report metadata
    report['date'] = report.get('date', datetime.now().isoformat())
    report['critical'] = report.get('critical', 'false') == 'true'

    # Step 3: Blockchain chaining
    patient = patients.find_one({'id': patient_id})
    previous_reports = patient.get('reports', []) if patient else []
    previous_hash = previous_reports[-1].get('reportHash') if previous_reports else 'GENESIS'
    report['previousHash'] = previous_hash

    hash_input = json.dumps(report, sort_keys=True).encode()
    report_hash = hashlib.sha256(hash_input).hexdigest()
    report['reportHash'] = report_hash

    # Step 4: Save to DB
    patients.update_one({'id': patient_id}, {'$push': {'reports': report}})
    return jsonify({'message': 'Report added and uploaded to IPFS', 'report': report}), 200

# ------------------- Run Server -------------------
from textblob import TextBlob
import speech_recognition as sr
import tempfile
import csv, json

@app.route('/analyze', methods=['POST'])
def analyze():
    voice_file = request.files.get('voice')
    message_file = request.files.get('messages')

    if not voice_file or not message_file:
        return jsonify({'error': 'Missing voice or message file'}), 400

    # -------- Voice Analysis --------
    recognizer = sr.Recognizer()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
        voice_file.save(temp_audio.name)
        with sr.AudioFile(temp_audio.name) as source:
            audio = recognizer.record(source)
            try:
                voice_text = recognizer.recognize_google(audio)
                voice_sentiment = TextBlob(voice_text).sentiment.polarity
            except Exception as e:
                return jsonify({'error': f"Voice processing failed: {str(e)}"}), 500

    # -------- Message File Analysis --------
    messages_text = ""
    filename = message_file.filename.lower()

    try:
        if filename.endswith('.txt'):
            messages_text = message_file.read().decode('utf-8')
        elif filename.endswith('.json'):
            data = json.load(message_file)
            messages_text = " ".join([str(msg) for msg in data.values()])
        elif filename.endswith('.csv'):
            decoded = message_file.read().decode('utf-8').splitlines()
            reader = csv.reader(decoded)
            messages_text = " ".join([" ".join(row) for row in reader])
        else:
            return jsonify({'error': 'Unsupported file type'}), 400
    except Exception as e:
        return jsonify({'error': f"Message file processing failed: {str(e)}"}), 500

    # -------- Sentiment Analysis --------
    message_blob = TextBlob(messages_text)
    message_sentiment = message_blob.sentiment.polarity

    return jsonify({
        'voice_text': voice_text,
        'voice_sentiment': "Positive" if voice_sentiment > 0 else "Negative" if voice_sentiment < 0 else "Neutral",
        'message_sentiment': "Positive" if message_sentiment > 0 else "Negative" if message_sentiment < 0 else "Neutral"
    }), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)
