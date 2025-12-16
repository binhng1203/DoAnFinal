from flask import Blueprint, request, jsonify
# from flask_jwt_extended import jwt_required
from src.models.report import TestRunHistory
from src.schemas.report import ReportSummarySchema, ReportDetailSchema

reports_bp = Blueprint('reports', __name__, url_prefix='/api/v1/reports')

@reports_bp.route('', methods=['GET'])
# @jwt_required()
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
            "total_items": pagination.total,
            "total_pages": pagination.pages
        }
    }), 200

@reports_bp.route('/<string:run_id_param>', methods=['GET'])
# @jwt_required()
def get_report_detail(run_id_param):
    """
    Lấy chi tiết report theo run_id (UUID string).
    """
    # [CHANGE] Query theo cột 'run_id' (UUID) thay vì 'id' (BigInt)
    # SQL mới đã có cột run_id text, nên ta dùng nó làm key tìm kiếm
    report = TestRunHistory.query.filter_by(run_id=run_id_param).first_or_404(description="Report not found")
    
    # Logic tối ưu: Nếu không heal, gán rỗng để chặn query thừa
    if not report.heal_attempted:
        report.heal_events = []
    
    # Visual events sẽ tự động load nhờ relationship lazy='select'
    
    return jsonify(ReportDetailSchema().dump(report)), 200