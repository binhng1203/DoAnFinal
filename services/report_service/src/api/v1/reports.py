from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from src.models.report import TestRunHistory, HealEvent, VisualValidationEvent
from src.schemas.report import ReportSummarySchema, ReportDetailSchema

reports_bp = Blueprint('reports', __name__, url_prefix='/api/v1/reports')

@reports_bp.route('', methods=['GET'])
# @jwt_required()  <-- Bật lại khi đã có Auth Service
def get_reports_list():
    test_id = request.args.get('test_id')
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)

    if not test_id:
        return jsonify({"error": "Missing test_id"}), 400

    query = TestRunHistory.query.filter_by(test_id=test_id).order_by(TestRunHistory.timestamp.desc())
    pagination = query.paginate(page=page, per_page=limit, error_out=False)

    return jsonify({
        "data": ReportSummarySchema(many=True).dump(pagination.items),
        "pagination": {
            "page": page,
            "total_pages": pagination.pages,
            "total_items": pagination.total
        }
    }), 200

@reports_bp.route('/<string:run_id>', methods=['GET'])
# @jwt_required()
def get_report_detail(run_id):
    report = TestRunHistory.query.filter_by(id=run_id).first_or_404()
    
    # Logic: Chỉ fetch heal_events nếu heal_attempted = True
    if not report.heal_attempted:
        report.heal_events = []
    
    return jsonify(ReportDetailSchema().dump(report)), 200