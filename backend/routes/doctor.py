from flask import Blueprint, request, jsonify, current_app

doctor_bp = Blueprint("doctor", __name__)

@doctor_bp.route("/", methods=["POST"])
def create_doctor():
    db = current_app.config["DB"]
    data = request.json
    result = db.doctors.insert_one(data)
    data["_id"] = str(result.inserted_id)
    return jsonify({"message": "Doctor created", "data": data}), 201

@doctor_bp.route("/", methods=["GET"])
def get_doctors():
    db = current_app.config["DB"]
    doctors = list(db.doctors.find())
    for doc in doctors:
        doc["_id"] = str(doc["_id"])
    return jsonify({"doctors": doctors})
