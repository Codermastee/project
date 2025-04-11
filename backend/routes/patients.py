from flask import Blueprint, request, jsonify, current_app

patients_bp = Blueprint("patients", __name__)

@patients_bp.route("/", methods=["POST"])
def create_patient():
    db = current_app.config["DB"]
    data = request.json

    if not data or not data.get("name"):
        return jsonify({"error": "Patient name is required"}), 400

    result = db.patients.insert_one(data)
    data["_id"] = str(result.inserted_id)
    return jsonify({"message": "Patient created", "data": data}), 201

@patients_bp.route("/", methods=["GET"])
def get_patients():
    db = current_app.config["DB"]
    patients = list(db.patients.find())
    for p in patients:
        p["_id"] = str(p["_id"])
    return jsonify({"patients": patients})
