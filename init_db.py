from app import app, init_sample_data
from models import db

with app.app_context():
    db.create_all()
    init_sample_data()
    print('数据库初始化完成，示例数据已添加')
