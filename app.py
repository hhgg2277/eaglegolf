import os
import requests
import secrets
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from models import db, User, Product, CartItem

NAVER_CLIENT_ID     = os.environ.get('NAVER_CLIENT_ID', 'de7FjoWV64zVLbB0S6Qr')
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET', 'xxuLoVGXav')
NAVER_REDIRECT_URI  = os.environ.get('NAVER_REDIRECT_URI', 'https://web-production-c9bdc.up.railway.app/login/naver/callback')

TOSS_CLIENT_KEY = os.environ.get('TOSS_CLIENT_KEY', 'test_ck_ALnQvDd2VJqjEndgyMQv3Mj7X41m')
TOSS_SECRET_KEY = os.environ.get('TOSS_SECRET_KEY', 'test_sk_PBal2vxj8116J6Wwq9Y285RQgOAN')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'local-dev-only-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///golfshop.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

db.init_app(app)

# uploads 폴더 자동 생성
os.makedirs(os.path.join(app.root_path, 'static', 'uploads'), exist_ok=True)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = '로그인이 필요합니다.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('관리자만 접근할 수 있습니다.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image(file):
    if file and allowed_file(file.filename):
        # 폴더 없으면 자동 생성
        upload_folder = app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        filename = secure_filename(file.filename)
        import time
        filename = f"{int(time.time())}_{filename}"
        path = os.path.join(upload_folder, filename)
        file.save(path)
        return filename
    return ''

# ── 홈 ──────────────────────────────────────────────
@app.route('/')
def index():
    best_products = Product.query.filter_by(is_best=True, is_active=True).limit(4).all()
    new_products  = Product.query.filter_by(is_new=True,  is_active=True).limit(4).all()
    if not new_products:
        new_products = Product.query.filter_by(is_active=True).order_by(Product.created.desc()).limit(4).all()
    categories = ['드라이버', '아이언', '퍼터', '웨지', '골프백', '골프화', '골프웨어', '액세서리']
    total_products = Product.query.filter_by(is_active=True).count()
    return render_template('index.html', best_products=best_products, new_products=new_products,
                           categories=categories, total_products=total_products)

# ── 상품 목록 ─────────────────────────────────────────
@app.route('/products')
def products():
    q        = request.args.get('q', '')
    category = request.args.get('category', '')
    query    = Product.query.filter_by(is_active=True)
    if q:
        query = query.filter(Product.name.contains(q))
    if category:
        query = query.filter_by(category=category)
    items = query.order_by(Product.created.desc()).all()
    categories = ['드라이버', '아이언', '퍼터', '웨지', '골프백', '골프화', '골프웨어', '액세서리']
    return render_template('products.html', products=items, q=q, category=category, categories=categories)

# ── 상품 상세 ─────────────────────────────────────────
@app.route('/product/<int:id>')
def product_detail(id):
    product = Product.query.get_or_404(id)
    related = Product.query.filter_by(category=product.category, is_active=True)\
                           .filter(Product.id != id).limit(4).all()
    return render_template('product_detail.html', product=product, related=related)

# ── 장바구니 ─────────────────────────────────────────
@app.route('/cart')
@login_required
def cart():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(i.product.price * i.quantity for i in items)
    return render_template('cart.html', items=items, total=total)

@app.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    product  = Product.query.get_or_404(product_id)
    quantity = int(request.form.get('quantity', 1))
    if quantity < 1: quantity = 1
    item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if item:
        item.quantity += quantity
    else:
        db.session.add(CartItem(user_id=current_user.id, product_id=product_id, quantity=quantity))
    db.session.commit()
    flash(f'장바구니에 {quantity}개 담았습니다.', 'success')
    return redirect(url_for('cart'))

@app.route('/cart/remove/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    item = CartItem.query.get_or_404(item_id)
    if item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for('cart'))

@app.route('/cart/update/<int:item_id>', methods=['POST'])
@login_required
def update_cart(item_id):
    item = CartItem.query.get_or_404(item_id)
    if item.user_id == current_user.id:
        qty = int(request.form.get('quantity', 1))
        if qty < 1:
            db.session.delete(item)
        else:
            item.quantity = qty
        db.session.commit()
    return redirect(url_for('cart'))

# ── 마이페이지 ────────────────────────────────────────
@app.route('/mypage')
@login_required
def mypage():
    cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
    return render_template('mypage.html', cart_count=cart_count)

# ── 회원가입 ──────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email    = request.form['email']
        username = request.form['username']
        password = request.form['password']
        confirm  = request.form['confirm']
        if password != confirm:
            flash('비밀번호가 일치하지 않습니다.', 'danger')
            return render_template('register.html')
        if len(password) < 6:
            flash('비밀번호는 6자 이상이어야 합니다.', 'danger')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('이미 사용 중인 이메일입니다.', 'danger')
            return render_template('register.html')
        if User.query.filter_by(username=username).first():
            flash('이미 사용 중인 닉네임입니다.', 'danger')
            return render_template('register.html')
        user = User(email=email, username=username, password=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f'{username}님, 환영합니다!', 'success')
        return redirect(url_for('index'))
    return render_template('register.html')

# ── 로그인 ────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']
        user     = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user, remember=request.form.get('remember'))
            flash(f'{user.username}님, 환영합니다!', 'success')
            return redirect(request.args.get('next') or url_for('index'))
        flash('이메일 또는 비밀번호가 올바르지 않습니다.', 'danger')
    return render_template('login.html')

# ── 로그아웃 ──────────────────────────────────────────
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('로그아웃되었습니다.', 'success')
    return redirect(url_for('index'))

# ── 네이버 로그인 ─────────────────────────────────────
@app.route('/login/naver')
def naver_login():
    state = secrets.token_hex(16)
    session['naver_state'] = state
    naver_auth_url = (
        f"https://nid.naver.com/oauth2.0/authorize"
        f"?response_type=code"
        f"&client_id={NAVER_CLIENT_ID}"
        f"&redirect_uri={NAVER_REDIRECT_URI}"
        f"&state={state}"
    )
    return redirect(naver_auth_url)

@app.route('/login/naver/callback')
def naver_callback():
    code  = request.args.get('code')
    state = request.args.get('state')
    if not code or state != session.get('naver_state'):
        flash('네이버 로그인에 실패했습니다.', 'danger')
        return redirect(url_for('login'))
    # 토큰 발급
    token_res = requests.post(
        'https://nid.naver.com/oauth2.0/token',
        params={
            'grant_type': 'authorization_code',
            'client_id': NAVER_CLIENT_ID,
            'client_secret': NAVER_CLIENT_SECRET,
            'code': code,
            'state': state,
        }
    ).json()
    access_token = token_res.get('access_token')
    if not access_token:
        flash('네이버 로그인에 실패했습니다.', 'danger')
        return redirect(url_for('login'))
    # 사용자 정보 가져오기
    profile_res = requests.get(
        'https://openapi.naver.com/v1/nid/me',
        headers={'Authorization': f'Bearer {access_token}'}
    ).json()
    naver_info = profile_res.get('response', {})
    naver_id    = naver_info.get('id', '')
    naver_email = naver_info.get('email', f'{naver_id}@naver.com')
    naver_name  = naver_info.get('name') or naver_info.get('nickname', '네이버유저')
    if not naver_id:
        flash('네이버 사용자 정보를 가져오지 못했습니다.', 'danger')
        return redirect(url_for('login'))
    # 기존 회원 확인 또는 자동 가입
    user = User.query.filter_by(email=naver_email).first()
    if not user:
        # 닉네임 중복 방지
        username = naver_name
        suffix = 1
        while User.query.filter_by(username=username).first():
            username = f'{naver_name}{suffix}'
            suffix += 1
        user = User(
            email    = naver_email,
            username = username,
            password = generate_password_hash(secrets.token_hex(16))
        )
        db.session.add(user)
        db.session.commit()
        flash(f'{username}님, 네이버로 회원가입되었습니다!', 'success')
    else:
        flash(f'{user.username}님, 네이버로 로그인되었습니다!', 'success')
    login_user(user)
    return redirect(url_for('index'))

# ════════════════════════════════════════════════════
#  관리자 페이지
# ════════════════════════════════════════════════════

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    total_products = Product.query.count()
    total_users    = User.query.count()
    total_cart     = CartItem.query.count()
    recent_products= Product.query.order_by(Product.created.desc()).limit(5).all()
    recent_users   = User.query.order_by(User.created.desc()).limit(5).all()
    return render_template('admin/dashboard.html',
                           total_products=total_products, total_users=total_users,
                           total_cart=total_cart, recent_products=recent_products,
                           recent_users=recent_users)

# ── 관리자 상품 목록 ──────────────────────────────────
@app.route('/admin/products')
@login_required
@admin_required
def admin_products():
    category = request.args.get('category', '')
    q        = request.args.get('q', '')
    query    = Product.query
    if category:
        query = query.filter_by(category=category)
    if q:
        query = query.filter(Product.name.contains(q))
    products  = query.order_by(Product.created.desc()).all()
    categories= ['드라이버', '아이언', '퍼터', '웨지', '골프백', '골프화', '골프웨어', '액세서리']
    return render_template('admin/products.html', products=products,
                           categories=categories, category=category, q=q)

# ── 관리자 상품 등록 ──────────────────────────────────
@app.route('/admin/products/new', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_new_product():
    categories = ['드라이버', '아이언', '퍼터', '웨지', '골프백', '골프화', '골프웨어', '액세서리']
    if request.method == 'POST':
        image_file = request.files.get('image')
        image_name = save_image(image_file) if image_file else ''
        product = Product(
            name        = request.form['name'],
            price       = int(request.form['price'].replace(',', '')),
            description = request.form['description'],
            category    = request.form['category'],
            stock       = int(request.form.get('stock', 0)),
            image       = image_name,
            is_best     = 'is_best' in request.form,
            is_new      = 'is_new' in request.form,
            is_active   = 'is_active' in request.form,
        )
        db.session.add(product)
        db.session.commit()
        flash('상품이 등록되었습니다.', 'success')
        return redirect(url_for('admin_products'))
    return render_template('admin/product_form.html', product=None, categories=categories, mode='new')

# ── 관리자 상품 수정 ──────────────────────────────────
@app.route('/admin/products/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_product(id):
    product    = Product.query.get_or_404(id)
    categories = ['드라이버', '아이언', '퍼터', '웨지', '골프백', '골프화', '골프웨어', '액세서리']
    if request.method == 'POST':
        image_file = request.files.get('image')
        if image_file and image_file.filename:
            # 기존 이미지 삭제
            if product.image:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], product.image)
                if os.path.exists(old_path):
                    os.remove(old_path)
            product.image = save_image(image_file)
        product.name        = request.form['name']
        product.price       = int(request.form['price'].replace(',', ''))
        product.description = request.form['description']
        product.category    = request.form['category']
        product.stock       = int(request.form.get('stock', 0))
        product.is_best     = 'is_best' in request.form
        product.is_new      = 'is_new' in request.form
        product.is_active   = 'is_active' in request.form
        db.session.commit()
        flash('상품이 수정되었습니다.', 'success')
        return redirect(url_for('admin_products'))
    return render_template('admin/product_form.html', product=product, categories=categories, mode='edit')

# ── 관리자 상품 삭제 ──────────────────────────────────
@app.route('/admin/products/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_product(id):
    product = Product.query.get_or_404(id)
    if product.image:
        path = os.path.join(app.config['UPLOAD_FOLDER'], product.image)
        if os.path.exists(path):
            os.remove(path)
    CartItem.query.filter_by(product_id=id).delete()
    db.session.delete(product)
    db.session.commit()
    flash('상품이 삭제되었습니다.', 'success')
    return redirect(url_for('admin_products'))

# ── 관리자 회원 목록 ──────────────────────────────────
@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.order_by(User.created.desc()).all()
    return render_template('admin/users.html', users=users)

# ── 관리자 회원 삭제 ──────────────────────────────────
@app.route('/admin/users/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(id):
    user = User.query.get_or_404(id)
    if user.is_admin:
        flash('관리자 계정은 삭제할 수 없습니다.', 'danger')
        return redirect(url_for('admin_users'))
    CartItem.query.filter_by(user_id=id).delete()
    db.session.delete(user)
    db.session.commit()
    flash('회원이 삭제되었습니다.', 'success')
    return redirect(url_for('admin_users'))

# ── 샘플 데이터 ───────────────────────────────────────
def create_sample_data():
    # 관리자 계정 없으면 무조건 생성
    if not User.query.filter_by(is_admin=True).first():
        admin = User(email='admin@golfshop.com', username='관리자',
                     password=generate_password_hash('admin1234'), is_admin=True)
        db.session.add(admin)
        db.session.flush()
        print("관리자 계정 생성 완료")
    if User.query.count() > 1:
        return
    admin = User.query.filter_by(is_admin=True).first()
    db.session.flush()
    samples = [
        ('타이틀리스트 TSR2 드라이버', 650000, '드라이버', 5, True,  False, '2024 신모델. 최고의 비거리와 정확성을 자랑하는 프리미엄 드라이버입니다.'),
        ('캘러웨이 패러다임 아이언 세트', 890000, '아이언',   3, True,  False, '7~PW 4개 세트. 관용성이 뛰어나 초·중급자에게 적합합니다.'),
        ('스코티카메론 퍼터 뉴포트 2', 450000, '퍼터',    8, True,  False, '투어 프로들이 즐겨 사용하는 블레이드 타입 퍼터입니다.'),
        ('클리블랜드 RTX6 웨지 56도', 180000, '웨지',    10, False, True,  '최신 스핀 기술 적용. 그린 주변 어떤 상황에서도 정확한 컨트롤이 가능합니다.'),
        ('타이틀리스트 스탠드백 14구', 320000, '골프백',   6, False, True,  '가볍고 내구성이 뛰어난 스탠드 타입 골프백. 14개 클럽 수납 가능.'),
        ('풋조이 프로/SL 골프화', 220000, '골프화',   7, True,  False, '투어 프로 선호 1위 골프화. 방수 기능과 뛰어난 그립감을 제공합니다.'),
        ('나이키 드라이핏 골프 폴로', 89000,  '골프웨어',  15, False, True,  '빠른 땀 흡수 드라이핏 소재. 4방향 스트레치로 스윙 시 불편함이 없습니다.'),
        ('볼빅 3피스 골프공 12구', 35000,  '액세서리',  50, False, True,  '고탄성 3피스 구조. 뛰어난 비거리와 부드러운 타감을 제공합니다.'),
    ]
    for name, price, cat, stock, best, new, desc in samples:
        p = Product(name=name, price=price, category=cat, stock=stock,
                    is_best=best, is_new=new, description=desc, image='')
        db.session.add(p)
    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_sample_data()
    app.run(debug=True)

# Railway 배포용 - 앱 시작 시 DB 자동 초기화
with app.app_context():
    db.create_all()
    create_sample_data()
