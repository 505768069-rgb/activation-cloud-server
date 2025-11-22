#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
激活码云端服务器
您部署这个服务器来管理激活码数据库
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import hashlib
import hmac
import json
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 密钥（必须与客户端一致）
SECRET_KEY = "SIQIU-2025-AI-ASSISTANT-SECRET-KEY-PLEASE-CHANGE"

# 云端数据库文件
DB_FILE = Path("cloud_activation_db.json")

def init_database():
    """初始化数据库"""
    if not DB_FILE.exists():
        initial_data = {
            "codes": {},
            "created_at": datetime.now().isoformat(),
            "version": "cloud_v1.0"
        }
        save_database(initial_data)

def load_database() -> dict:
    """加载数据库"""
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"codes": {}, "version": "cloud_v1.0"}

def save_database(data: dict):
    """保存数据库"""
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def hash_code(code: str) -> str:
    """计算激活码哈希"""
    return hashlib.sha256(code.encode()).hexdigest()

def generate_signature(data: str) -> str:
    """生成签名"""
    return hmac.new(
        SECRET_KEY.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()[:16].upper()

@app.route('/api/verify', methods=['POST'])
def verify_code():
    """验证激活码"""
    try:
        data = request.json
        code = data.get('code', '').strip().upper()
        
        if not code:
            return jsonify({
                "valid": False,
                "message": "激活码不能为空"
            }), 400
        
        # 解析激活码
        parts = code.split('-')
        if len(parts) != 5:
            return jsonify({
                "valid": False,
                "message": "激活码格式错误"
            }), 400
        
        prefix, type_code, timestamp, salt, signature = parts
        
        # 验证签名
        sign_data = f"{prefix}-{type_code}-{timestamp}-{salt}"
        expected_signature = generate_signature(sign_data)
        
        if signature != expected_signature:
            return jsonify({
                "valid": False,
                "message": "激活码无效（签名验证失败）"
            }), 400
        
        # 检查数据库中的使用状态
        db = load_database()
        code_hash = hash_code(code)
        
        if code_hash in db["codes"]:
            code_info = db["codes"][code_hash]
            if code_info.get("used", False):
                return jsonify({
                    "valid": False,
                    "message": f"激活码已被使用（使用时间：{code_info.get('used_at', '未知')}）"
                }), 400
        
        # 解析类型
        if type_code == "P000":
            code_type = "永久"
            days = 0
        elif type_code.startswith('D'):
            code_type = "试用"
            days = int(type_code[1:])
        else:
            return jsonify({
                "valid": False,
                "message": "激活码类型错误"
            }), 400
        
        return jsonify({
            "valid": True,
            "type": code_type,
            "days": days,
            "message": f"{'永久激活码' if days == 0 else f'{days}天试用激活码'}"
        }), 200
    
    except Exception as e:
        return jsonify({
            "valid": False,
            "message": f"验证失败：{str(e)}"
        }), 500

@app.route('/api/activate', methods=['POST'])
def activate_code():
    """标记激活码为已使用"""
    try:
        data = request.json
        code = data.get('code', '').strip().upper()
        
        if not code:
            return jsonify({
                "success": False,
                "message": "激活码不能为空"
            }), 400
        
        db = load_database()
        code_hash = hash_code(code)
        
        # 如果数据库中没有这个激活码，先添加
        if code_hash not in db["codes"]:
            # 解析类型
            parts = code.split('-')
            if len(parts) == 5:
                type_code = parts[1]
                if type_code == "P000":
                    code_type = "永久"
                    days = 0
                elif type_code.startswith('D'):
                    code_type = "试用"
                    days = int(type_code[1:])
                else:
                    code_type = "未知"
                    days = 0
                
                db["codes"][code_hash] = {
                    "type": code_type,
                    "code": code,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "used": False
                }
                if days > 0:
                    db["codes"][code_hash]["days"] = days
        
        # 标记为已使用
        db["codes"][code_hash]["used"] = True
        db["codes"][code_hash]["used_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db["codes"][code_hash]["used_by"] = request.remote_addr
        
        save_database(db)
        
        return jsonify({
            "success": True,
            "message": "激活码已标记为使用"
        }), 200
    
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"标记失败：{str(e)}"
        }), 500

@app.route('/api/admin/generate', methods=['POST'])
def admin_generate():
    """管理员生成激活码"""
    try:
        data = request.json
        count = data.get('count', 1)
        days = data.get('days', 0)
        prefix = data.get('prefix', 'SIQIU')
        
        # 生成激活码
        import secrets
        codes = []
        db = load_database()
        
        for i in range(count):
            # 类型代码
            if days == 0:
                type_code = "P000"
            else:
                type_code = f"D{days:03d}"
            
            # 时间戳
            timestamp = datetime.now().strftime("%Y%m%d")
            
            # 随机盐
            salt = secrets.token_hex(4).upper()
            
            # 生成签名
            sign_data = f"{prefix}-{type_code}-{timestamp}-{salt}"
            signature = generate_signature(sign_data)
            
            # 完整激活码
            code = f"{prefix}-{type_code}-{timestamp}-{salt}-{signature}"
            codes.append(code)
            
            # 添加到数据库
            code_hash = hash_code(code)
            db["codes"][code_hash] = {
                "type": "永久" if days == 0 else "试用",
                "code": code,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "used": False,
                "used_at": None,
                "used_by": None
            }
            
            if days > 0:
                db["codes"][code_hash]["days"] = days
        
        save_database(db)
        
        return jsonify({
            "success": True,
            "count": len(codes),
            "codes": codes,
            "message": f"成功生成 {len(codes)} 个激活码"
        }), 200
    
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"生成失败：{str(e)}"
        }), 500

@app.route('/api/admin/list', methods=['GET'])
def admin_list():
    """管理员查看所有激活码"""
    try:
        db = load_database()
        return jsonify({
            "success": True,
            "codes": db["codes"],
            "total": len(db["codes"])
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"查询失败：{str(e)}"
        }), 500

@app.route('/api/admin/statistics', methods=['GET'])
def admin_statistics():
    """管理员查看统计信息"""
    try:
        db = load_database()
        codes = db["codes"]
        
        total = len(codes)
        used = sum(1 for c in codes.values() if c.get("used", False))
        unused = total - used
        
        by_type = {}
        for code_info in codes.values():
            type_name = code_info.get("type", "未知")
            by_type[type_name] = by_type.get(type_name, 0) + 1
        
        return jsonify({
            "success": True,
            "statistics": {
                "total": total,
                "used": used,
                "unused": unused,
                "usage_rate": f"{(used/total*100):.1f}%" if total > 0 else "0%",
                "by_type": by_type
            }
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"统计失败：{str(e)}"
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "service": "激活码云端服务",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }), 200

if __name__ == '__main__':
    print("=" * 70)
    print("🚀 激活码云端服务器".center(70))
    print("=" * 70)
    print()
    
    # 初始化数据库
    init_database()
    print("✅ 数据库初始化完成")
    print(f"📁 数据库文件: {DB_FILE.absolute()}")
    print()
    
    print("🌐 API端点:")
    print("  POST /api/verify        - 验证激活码")
    print("  POST /api/activate      - 标记激活码为已使用")
    print("  POST /api/admin/generate - 生成激活码")
    print("  GET  /api/admin/list    - 查看所有激活码")
    print("  GET  /api/admin/statistics - 查看统计信息")
    print("  GET  /api/health        - 健康检查")
    print()
    
    print("=" * 70)
    print()
    print("🔧 启动服务器...")
    print()
    
    # 启动服务器
    app.run(
        host='0.0.0.0',  # 允许外部访问
        port=5000,
        debug=True
    )
