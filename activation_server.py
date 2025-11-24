#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
激活码云端验证服务器
部署到 Render.com，为客户端EXE提供激活码验证服务
"""

import os
import json
import hashlib
import hmac
from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path
from datetime import datetime, timedelta
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)
CORS(app)

# 激活密钥（必须与客户端一致）
SECRET_KEY = os.getenv(
    "ACTIVATION_SECRET_KEY",
    "SIQIU-2025-AI-ASSISTANT-SECRET-KEY-PLEASE-CHANGE"
)

# 激活数据库文件
DB_FILE = Path("cloud_activation_db.json")


class ActivationDatabase:
    """激活码数据库管理"""
    
    def __init__(self, db_file):
        self.db_file = db_file
        self.load_database()
    
    def load_database(self):
        """加载数据库"""
        if self.db_file.exists():
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    self.db = json.load(f)
                logger.info(f"✅ 加载激活数据库: {len(self.db.get('codes', {}))} 个激活码")
            except Exception as e:
                logger.error(f"❌ 加载数据库失败: {e}")
                self.db = {"codes": {}, "logs": []}
        else:
            self.db = {"codes": {}, "logs": []}
            self.save_database()
            logger.info("✅ 创建新的激活数据库")
    
    def save_database(self):
        """保存数据库"""
        try:
            self.db_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(self.db, f, ensure_ascii=False, indent=2)
            logger.info("✅ 数据库已保存")
        except Exception as e:
            logger.error(f"❌ 保存数据库失败: {e}")
    
    def add_code(self, code, type_name, duration_days, notes=""):
        """添加激活码"""
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        self.db["codes"][code_hash] = {
            "code": code,
            "type": type_name,
            "duration_days": duration_days,
            "notes": notes,
            "generated_at": datetime.now().isoformat(),
            "activated": False,
            "activated_at": None,
            "device_id": None
        }
        self.save_database()
        logger.info(f"✅ 添加激活码: {code[:10]}... (类型:{type_name}, 天数:{duration_days})")
    
    def verify_code(self, code):
        """验证激活码"""
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        
        if code_hash not in self.db["codes"]:
            return {"valid": False, "message": "激活码不存在"}
        
        code_info = self.db["codes"][code_hash]
        
        if code_info["activated"]:
            # 检查是否过期
            activated_at = datetime.fromisoformat(code_info["activated_at"])
            expire_at = activated_at + timedelta(days=code_info["duration_days"])
            
            if datetime.now() > expire_at:
                return {
                    "valid": False,
                    "message": "激活码已过期",
                    "type": code_info["type"]
                }
            
            return {
                "valid": True,
                "message": "激活码有效",
                "type": code_info["type"],
                "activated_at": code_info["activated_at"],
                "expire_at": expire_at.isoformat()
            }
        
        # 未激活的码，激活它
        code_info["activated"] = True
        code_info["activated_at"] = datetime.now().isoformat()
        self.save_database()
        
        expire_at = datetime.now() + timedelta(days=code_info["duration_days"])
        
        logger.info(f"✅ 激活成功: {code[:10]}... (类型:{code_info['type']})")
        
        return {
            "valid": True,
            "message": f"激活成功！({code_info['type']}, 有效期{code_info['duration_days']}天)",
            "type": code_info["type"],
            "activated_at": code_info["activated_at"],
            "expire_at": expire_at.isoformat()
        }
    
    def list_codes(self):
        """列出所有激活码"""
        codes = []
        for code_hash, info in self.db["codes"].items():
            codes.append({
                "code": info["code"],
                "type": info["type"],
                "duration_days": info["duration_days"],
                "notes": info["notes"],
                "generated_at": info["generated_at"],
                "activated": info["activated"],
                "activated_at": info["activated_at"]
            })
        return codes
    
    def add_log(self, action, details):
        """添加日志"""
        self.db["logs"].append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details
        })
        # 只保留最近1000条日志
        if len(self.db["logs"]) > 1000:
            self.db["logs"] = self.db["logs"][-1000:]
        self.save_database()


# 初始化数据库
db = ActivationDatabase(DB_FILE)


def generate_signature(data: str) -> str:
    """生成签名"""
    return hmac.new(
        SECRET_KEY.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()[:16].upper()


def generate_activation_code(type_code: str, duration_days: int) -> str:
    """生成激活码"""
    prefix = "SIQIU"
    timestamp = datetime.now().strftime("%y%m%d")
    
    # 生成随机盐值
    import random
    import string
    salt = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    
    # 生成签名
    sign_data = f"{prefix}-{type_code}-{timestamp}-{salt}"
    signature = generate_signature(sign_data)
    
    # 组合激活码
    code = f"{prefix}-{type_code}-{timestamp}-{salt}-{signature}"
    
    return code


# ========== API路由 ==========

@app.route('/')
def index():
    """首页"""
    return jsonify({
        "service": "工作AI助手 - 激活验证服务",
        "version": "1.0.0",
        "status": "running",
        "codes_count": len(db.db["codes"]),
        "endpoints": {
            "verify": "/api/verify",
            "generate": "/api/generate",
            "list": "/api/list",
            "health": "/api/health"
        }
    })


@app.route('/api/health')
def health():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "codes_count": len(db.db["codes"]),
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/verify', methods=['POST'])
def verify_activation():
    """验证激活码"""
    try:
        data = request.json
        code = data.get('code', '').strip().upper()
        
        if not code:
            return jsonify({
                "valid": False,
                "message": "激活码不能为空"
            }), 400
        
        logger.info(f"🔍 验证激活码: {code[:10]}...")
        
        # 基本格式检查
        parts = code.split('-')
        if len(parts) != 5:
            return jsonify({
                "valid": False,
                "message": "激活码格式错误"
            })
        
        prefix, type_code, timestamp, salt, signature = parts
        
        # 验证签名
        sign_data = f"{prefix}-{type_code}-{timestamp}-{salt}"
        expected_signature = generate_signature(sign_data)
        
        if signature != expected_signature:
            logger.warning(f"⚠️  签名验证失败: {code[:10]}...")
            return jsonify({
                "valid": False,
                "message": "激活码签名验证失败"
            })
        
        # 从数据库验证
        result = db.verify_code(code)
        
        # 记录日志
        db.add_log("verify", {
            "code": code[:10] + "...",
            "result": result["valid"],
            "message": result["message"]
        })
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"❌ 验证失败: {str(e)}")
        return jsonify({
            "valid": False,
            "message": f"服务器错误: {str(e)}"
        }), 500


@app.route('/api/generate', methods=['POST'])
def generate_code():
    """生成激活码（需要管理员密码）"""
    try:
        data = request.json
        admin_password = data.get('admin_password', '')
        
        # 简单的管理员验证（生产环境建议使用更强的认证）
        if admin_password != os.getenv('ADMIN_PASSWORD', 'admin123'):
            return jsonify({
                "success": False,
                "message": "管理员密码错误"
            }), 401
        
        type_code = data.get('type', 'TRIAL')
        duration_days = data.get('duration_days', 7)
        notes = data.get('notes', '')
        count = data.get('count', 1)
        
        # 类型映射
        type_map = {
            "trial": ("TRIAL", "试用版"),
            "month": ("MONTH", "月度版"),
            "year": ("YEAR", "年度版"),
            "permanent": ("PERM", "永久版")
        }
        
        type_code_short, type_name = type_map.get(type_code.lower(), ("TRIAL", "试用版"))
        
        # 生成激活码
        codes = []
        for i in range(count):
            code = generate_activation_code(type_code_short, duration_days)
            db.add_code(code, type_name, duration_days, notes)
            codes.append(code)
        
        logger.info(f"✅ 生成 {count} 个激活码: {type_name}")
        
        return jsonify({
            "success": True,
            "message": f"成功生成 {count} 个激活码",
            "codes": codes,
            "type": type_name,
            "duration_days": duration_days
        })
        
    except Exception as e:
        logger.error(f"❌ 生成激活码失败: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"生成失败: {str(e)}"
        }), 500


@app.route('/api/list', methods=['POST'])
def list_codes():
    """列出所有激活码（需要管理员密码）"""
    try:
        data = request.json
        admin_password = data.get('admin_password', '')
        
        if admin_password != os.getenv('ADMIN_PASSWORD', 'admin123'):
            return jsonify({
                "success": False,
                "message": "管理员密码错误"
            }), 401
        
        codes = db.list_codes()
        
        return jsonify({
            "success": True,
            "codes": codes,
            "total": len(codes)
        })
        
    except Exception as e:
        logger.error(f"❌ 获取激活码列表失败: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"获取失败: {str(e)}"
        }), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取统计信息（无需密码）"""
    try:
        total_codes = len(db.db["codes"])
        activated_codes = sum(1 for c in db.db["codes"].values() if c["activated"])
        
        return jsonify({
            "total_codes": total_codes,
            "activated_codes": activated_codes,
            "unused_codes": total_codes - activated_codes
        })
        
    except Exception as e:
        logger.error(f"❌ 获取统计失败: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"获取失败: {str(e)}"
        }), 500


# ========== 错误处理 ==========

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "接口不存在"}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"服务器错误: {str(error)}")
    return jsonify({"error": "服务器内部错误"}), 500


# ========== 启动服务器 ==========

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'
    
    logger.info("=" * 60)
    logger.info("🚀 激活验证服务器启动")
    logger.info("=" * 60)
    logger.info(f"📡 端口: {port}")
    logger.info(f"🔧 调试模式: {debug}")
    logger.info(f"📦 已加载激活码: {len(db.db['codes'])} 个")
    logger.info(f"🔑 密钥已设置: {'✅' if SECRET_KEY else '❌'}")
    logger.info("=" * 60)
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
