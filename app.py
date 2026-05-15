import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from models import db, Book, Reader, Borrow

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'library-management-secret-key-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    f'sqlite:///{os.path.join(BASE_DIR, "library.db")}'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)


# ==================== 首页仪表盘 ====================

@app.route('/')
def index():
    total_books = Book.query.count()
    total_readers = Reader.query.count()
    active_borrows = Borrow.query.filter_by(status='借阅中').count()
    today = datetime.utcnow()
    overdue_borrows = Borrow.query.filter(
        Borrow.status == '借阅中',
        Borrow.due_date < today
    ).count()
    recent_borrows = Borrow.query.order_by(Borrow.borrow_date.desc()).limit(10).all()
    return render_template('index.html',
                           total_books=total_books,
                           total_readers=total_readers,
                           active_borrows=active_borrows,
                           overdue_borrows=overdue_borrows,
                           recent_borrows=recent_borrows,
                           now=datetime.utcnow())


# ==================== 图书管理 ====================

@app.route('/books')
def book_list():
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    query = Book.query
    if search:
        query = query.filter(
            db.or_(
                Book.title.contains(search),
                Book.author.contains(search),
                Book.isbn.contains(search),
                Book.publisher.contains(search)
            )
        )
    if category:
        query = query.filter_by(category=category)
    books = query.order_by(Book.created_at.desc()).all()
    categories = sorted(set(
        r[0] for r in db.session.query(Book.category).distinct() if r[0]
    ))
    return render_template('books.html', books=books, search=search,
                           category=category, categories=categories)


@app.route('/books/add', methods=['GET', 'POST'])
def book_add():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        isbn = request.form.get('isbn', '').strip()
        publisher = request.form.get('publisher', '').strip()
        category = request.form.get('category', '').strip()
        try:
            total_qty = int(request.form.get('total_quantity', 1))
        except ValueError:
            total_qty = 1

        if not title or not author or not isbn:
            flash('书名、作者和ISBN为必填项', 'danger')
            return render_template('book_form.html', book=None)

        if Book.query.filter_by(isbn=isbn).first():
            flash(f'ISBN "{isbn}" 已存在', 'danger')
            return render_template('book_form.html', book=None)

        book = Book(
            title=title, author=author, isbn=isbn,
            publisher=publisher, category=category,
            total_quantity=total_qty, available_quantity=total_qty
        )
        db.session.add(book)
        db.session.commit()
        flash('图书添加成功', 'success')
        return redirect(url_for('book_list'))

    return render_template('book_form.html', book=None)


@app.route('/books/<int:book_id>/edit', methods=['GET', 'POST'])
def book_edit(book_id):
    book = Book.query.get_or_404(book_id)
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        isbn = request.form.get('isbn', '').strip()
        publisher = request.form.get('publisher', '').strip()
        category = request.form.get('category', '').strip()
        try:
            new_total = int(request.form.get('total_quantity', 1))
        except ValueError:
            new_total = book.total_quantity

        if not title or not author or not isbn:
            flash('书名、作者和ISBN为必填项', 'danger')
            return render_template('book_form.html', book=book)

        existing = Book.query.filter_by(isbn=isbn).first()
        if existing and existing.id != book.id:
            flash(f'ISBN "{isbn}" 已被其他图书使用', 'danger')
            return render_template('book_form.html', book=book)

        borrowed_count = book.total_quantity - book.available_quantity
        if new_total < borrowed_count:
            flash(f'总数量不能小于当前借出数量({borrowed_count})', 'danger')
            return render_template('book_form.html', book=book)

        book.title = title
        book.author = author
        book.isbn = isbn
        book.publisher = publisher
        book.category = category
        book.total_quantity = new_total
        book.available_quantity = new_total - borrowed_count
        db.session.commit()
        flash('图书更新成功', 'success')
        return redirect(url_for('book_list'))

    return render_template('book_form.html', book=book)


@app.route('/books/<int:book_id>/delete', methods=['POST'])
def book_delete(book_id):
    book = Book.query.get_or_404(book_id)
    active = Borrow.query.filter_by(book_id=book_id, status='借阅中').count()
    if active > 0:
        flash(f'该图书有 {active} 条未归还借阅记录，无法删除', 'danger')
    else:
        db.session.delete(book)
        db.session.commit()
        flash('图书删除成功', 'success')
    return redirect(url_for('book_list'))


# ==================== 读者管理 ====================

@app.route('/readers')
def reader_list():
    search = request.args.get('search', '').strip()
    query = Reader.query
    if search:
        query = query.filter(
            db.or_(
                Reader.name.contains(search),
                Reader.phone.contains(search),
                Reader.email.contains(search)
            )
        )
    readers = query.order_by(Reader.created_at.desc()).all()
    return render_template('readers.html', readers=readers, search=search)


@app.route('/readers/add', methods=['GET', 'POST'])
def reader_add():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        if not name:
            flash('姓名为必填项', 'danger')
            return render_template('reader_form.html', reader=None)
        reader = Reader(name=name, phone=phone, email=email)
        db.session.add(reader)
        db.session.commit()
        flash('读者添加成功', 'success')
        return redirect(url_for('reader_list'))
    return render_template('reader_form.html', reader=None)


@app.route('/readers/<int:reader_id>/edit', methods=['GET', 'POST'])
def reader_edit(reader_id):
    reader = Reader.query.get_or_404(reader_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        if not name:
            flash('姓名为必填项', 'danger')
            return render_template('reader_form.html', reader=reader)
        reader.name = name
        reader.phone = phone
        reader.email = email
        db.session.commit()
        flash('读者信息更新成功', 'success')
        return redirect(url_for('reader_list'))
    return render_template('reader_form.html', reader=reader)


@app.route('/readers/<int:reader_id>/delete', methods=['POST'])
def reader_delete(reader_id):
    reader = Reader.query.get_or_404(reader_id)
    active = Borrow.query.filter_by(reader_id=reader_id, status='借阅中').count()
    if active > 0:
        flash(f'该读者有 {active} 本图书未归还，无法删除', 'danger')
    else:
        db.session.delete(reader)
        db.session.commit()
        flash('读者删除成功', 'success')
    return redirect(url_for('reader_list'))


# ==================== 借阅管理 ====================

@app.route('/borrows')
def borrow_list():
    status_filter = request.args.get('status', '').strip()
    query = Borrow.query
    if status_filter == '借阅中':
        query = query.filter_by(status='借阅中')
    elif status_filter == '已归还':
        query = query.filter_by(status='已归还')
    borrows = query.order_by(Borrow.borrow_date.desc()).all()
    return render_template('borrows.html', borrows=borrows, status_filter=status_filter,
                           now=datetime.utcnow())


@app.route('/borrows/add', methods=['GET', 'POST'])
def borrow_add():
    books = Book.query.filter(Book.available_quantity > 0).order_by(Book.title).all()
    readers = Reader.query.order_by(Reader.name).all()

    if request.method == 'POST':
        book_id = request.form.get('book_id', type=int)
        reader_id = request.form.get('reader_id', type=int)
        due_days = request.form.get('due_days', 30, type=int)

        book = Book.query.get(book_id) if book_id else None
        reader = Reader.query.get(reader_id) if reader_id else None

        if not book or not reader:
            flash('请选择图书和读者', 'danger')
            return render_template('borrow_form.html', books=books, readers=readers)

        if book.available_quantity <= 0:
            flash('该图书已无可用库存', 'danger')
            return render_template('borrow_form.html', books=books, readers=readers)

        borrow = Borrow(
            book_id=book_id,
            reader_id=reader_id,
            borrow_date=datetime.utcnow(),
            due_date=datetime.utcnow() + timedelta(days=due_days),
            status='借阅中'
        )
        book.available_quantity -= 1
        db.session.add(borrow)
        db.session.commit()
        flash('借阅成功', 'success')
        return redirect(url_for('borrow_list'))

    return render_template('borrow_form.html', books=books, readers=readers)


@app.route('/borrows/<int:borrow_id>/return', methods=['POST'])
def borrow_return(borrow_id):
    borrow = Borrow.query.get_or_404(borrow_id)
    if borrow.status == '已归还':
        flash('该记录已归还', 'warning')
    else:
        borrow.status = '已归还'
        borrow.return_date = datetime.utcnow()
        borrow.book.available_quantity += 1
        db.session.commit()
        flash('归还成功', 'success')
    return redirect(url_for('borrow_list'))


# ==================== 搜索 API ====================

@app.route('/api/books/search')
def api_book_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    books = Book.query.filter(
        db.or_(
            Book.title.contains(q),
            Book.author.contains(q),
            Book.isbn.contains(q)
        )
    ).limit(20).all()
    return jsonify([b.to_dict() for b in books])


# ==================== 初始化数据库 ====================

def init_sample_data():
    """初始化示例数据"""
    if Book.query.count() > 0:
        return

    sample_books = [
        Book(title='红楼梦', author='曹雪芹', isbn='978-7-02-000220-7',
             publisher='人民文学出版社', category='文学', total_quantity=5, available_quantity=5),
        Book(title='三国演义', author='罗贯中', isbn='978-7-02-000221-4',
             publisher='人民文学出版社', category='文学', total_quantity=3, available_quantity=3),
        Book(title='西游记', author='吴承恩', isbn='978-7-02-000222-1',
             publisher='人民文学出版社', category='文学', total_quantity=4, available_quantity=4),
        Book(title='数据结构与算法', author='严蔚敏', isbn='978-7-302-14751-0',
             publisher='清华大学出版社', category='计算机', total_quantity=2, available_quantity=2),
        Book(title='深入理解计算机系统', author='Randal E. Bryant', isbn='978-7-111-54493-7',
             publisher='机械工业出版社', category='计算机', total_quantity=2, available_quantity=2),
        Book(title='三体', author='刘慈欣', isbn='978-7-5366-9293-0',
             publisher='重庆出版社', category='科幻', total_quantity=6, available_quantity=6),
    ]

    sample_readers = [
        Reader(name='张三', phone='13800138001', email='zhangsan@example.com'),
        Reader(name='李四', phone='13800138002', email='lisi@example.com'),
        Reader(name='王五', phone='13800138003', email='wangwu@example.com'),
    ]

    for b in sample_books:
        db.session.add(b)
    for r in sample_readers:
        db.session.add(r)
    db.session.commit()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_sample_data()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
