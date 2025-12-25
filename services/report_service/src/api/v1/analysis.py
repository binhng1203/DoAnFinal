from flask import Blueprint, request, jsonify
from src.services.analysis import AnalysisService

analysis_bp = Blueprint('analysis', __name__, url_prefix='/api/v1/analysis')

@analysis_bp.route('', methods=['GET'])
def get_analysis_by_testcase():
    """
    RS_03: Xem danh sách analysis của 1 testcase
    Input: test_id (required), page, limit
    """
    case_id = request.args.get('case_id', type=int)
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)

    if case_id is None:
        return jsonify({"error": "Missing or invalid case_id param (must be integer)"}), 400

    data, total = AnalysisService.get_analysis_list(case_id, page, limit)

    return jsonify({
        "data": data,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_items": total,
            "total_pages": (total + limit - 1) // limit
        }
    }), 200

@analysis_bp.route('/<string:analysis_id>', methods=['GET'])
def get_analysis_detail(analysis_id):
    """
    RS_04: Xem chi tiết 1 analysis (có context test_id)
    Input: analysis_id (path), test_id (query param)
    """
    
    
    result = AnalysisService.get_analysis_detail(analysis_id)
    
    if not result:
        return jsonify({"error": "Analysis not found"}), 404
        
    return jsonify(result), 200