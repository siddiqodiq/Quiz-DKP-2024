import datetime
import uuid
import os
from flask import Flask, request, render_template, make_response, redirect

from peewee import *

db = SqliteDatabase("b.db")


class User(Model):
    id = AutoField()
    username = CharField(unique=True)
    password = CharField()
    token = CharField()
    balance = IntegerField()

    class Meta:
        database = db


class PurchaseLog(Model):
    id = AutoField()
    user_id = IntegerField()
    product_id = IntegerField()
    paid_amount = IntegerField()
    v_date = DateField(default=datetime.datetime.now)
    lock = CharField()

    class Meta:
        database = db


class Product(Model):
    id = AutoField()
    name = CharField(unique=True)
    price = IntegerField()

    class Meta:
        database = db


@db.connection_context()
def initialize():
    db.create_tables([User, PurchaseLog, Product])
    for i in [
        {
            "name": "Galois Salad", "price": 5,
        },
        {
            "name": "Alpaca Salad", "price": 20,
        },
        {
            "name": "Flag", "price": 21,
        }
    ]:
        try:
            Product.create(name=i["name"], price=i["price"])
        except:
            pass


initialize()


class API:
    @staticmethod
    @db.connection_context()
    def login(username, password) -> str:
        user_objs = User \
            .select() \
            .where(User.username == username)
        if len(user_objs) == 0:
            token = str(uuid.uuid4())
            try:
                User.create(
                    username=username,
                    password=password,
                    token=token,
                    balance=20,
                )
            except IntegrityError as e:
                print(e)
                return ""
            return token
        user_obj = user_objs[0]
        if user_obj.password != password:
            return ""
        return user_obj.token

    @staticmethod
    @db.connection_context()
    def get_user_detail_by_token(token: str) -> (bool, int, [PurchaseLog]):
        user_objs = User \
            .select() \
            .where(User.token == token)
        if len(user_objs) == 0:
            return False, 0, None
        user_obj = user_objs[0]
        purchase_log = PurchaseLog \
            .select() \
            .where(PurchaseLog.user_id == user_obj.id)
        return True, user_obj.balance, [x for x in purchase_log]

    @staticmethod
    @db.connection_context()
    def sell(token: str, purchase_id: int) -> (bool, str):
        user_objs = User \
        .select() \
        .where(User.token == token)
        if len(user_objs) == 0:
            return False, "Wrong Token"
        user_obj = user_objs[0]
        lock_val = uuid.uuid1()
        
        #got_lock is the number of lines updated
        got_lock = PurchaseLog \
        .update(lock=lock_val) \
        .where(PurchaseLog.id == purchase_id) \
        .where(PurchaseLog.user_id == user_obj.id) \
        .where(PurchaseLog.token == "") \
        .execute()
        if got_lock != 1:
            return False, "Item not found, or lock not aquired"
        purchases = PurchaseLog\
            .select()\
            .where(PurchaseLog.id == purchase_id)
        purchase = purchases[0]
        #sanity check
        if lock_val != purchase.lock:
            False, "Lock sanity check failed"
        PurchaseLog\
            .delete()\
            .where(PurchaseLog.id == purchase_id)\
            .execute()
        User \
            .update(balance=user_obj.balance + purchase.paid_amount) \
            .where(User.id == user_obj.id) \
            .execute()
        if purchase.paid_amount == 21:
            return False, f"Well, flag is {os.getenv('FLAG')}"
            
        return True, ""

    @staticmethod
    @db.connection_context()
    def sell(purchase_id: int) -> (bool, str):
        purchase_history_objs = PurchaseLog \
            .select() \
            .where(PurchaseLog.id == purchase_id)
        if len(purchase_history_objs) == 0:
            return False, "No such product"
        purchase_history_obj = purchase_history_objs[0]

        user_objs = User \
            .select()
        if len(user_objs) == 0:
            return False, "Wrong Token"

        user_obj = user_objs[0]

        if purchase_history_obj.user_id != user_obj.id:
            return False, "Not the purchase you made bro..."

        PurchaseLog\
            .delete()\
            .where(PurchaseLog.id == purchase_history_obj.id)\
            .execute()

        User \
            .update(balance=user_obj.balance + purchase_history_obj.paid_amount) \
            .where(User.id == user_obj.id) \
            .execute()
        if purchase_history_obj.paid_amount == 21:
            return False, f"Well, flag is {os.getenv('FLAG')}"
        return True, ""


app = Flask(__name__)


@app.route('/', methods=["GET", "POST"])
def default():
    if request.method == 'POST':
        token = API.login(request.form["username"], request.form["password"])
        if token:
            resp = make_response(redirect("/"))
            resp.set_cookie("token", token)
            return resp
        else:
            return render_template('login.html',
                                   error_msg="Wrong credential")
        pass
    else:
        token = request.cookies.get("token")

        def go_login():
            return render_template('login.html')

        if token and len(token) > 5:
            is_login, balance, purchase_log = API.get_user_detail_by_token(token)
            if not is_login:
                resp = make_response(redirect("/"))
                resp.set_cookie("token", "")
                return resp
            return render_template('home.html', balance=balance, purchase_log=purchase_log)
        return go_login()


@app.route('/buy/<product_id>', methods=["GET"])
def buy(product_id):
    is_success, err_message = API.buy(int(product_id))
    if is_success:
        return make_response(redirect("/"))
    else:
        return err_message


@app.route('/sell/<purchase_id>', methods=["GET"])
def sell(purchase_id):
    is_success, err_message = API.sell(int(purchase_id))
    if is_success:
        return make_response(redirect("/"))
    else:
        return err_message
