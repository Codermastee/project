from flask import Blueprint, request, jsonify, current_app

users_bp = Blueprint("users", __name__)

@users_bp.route("/", methods=["POST"])
def create_user():
    db = current_app.config["DB"]
    data = request.json
    result = db.users.insert_one(data)
    data["_id"] = str(result.inserted_id)
    return jsonify({"message": "User created", "data": data}), 201

@users_bp.route("/", methods=["GET"])
def get_users():
    db = current_app.config["DB"]
    users = list(db.users.find())
    for u in users:
        u["_id"] = str(u["_id"])
    return jsonify({"users": users})
