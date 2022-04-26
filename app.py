import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods = ["GET","POST"])
@login_required
def index():
    """Show portfolio of stocks"""
    if request.method == ("POST"):
        userid = session["user_id"]
        cashadded = int(request.form.get("addcash"))
        if cashadded > 10000 or cashadded < 0:
            return apology ("Cannot add more than $10,000 at once and cannot add negative or zero cash")
        getcash = db.execute("SELECT cash FROM users WHERE id = ?", userid)
        currentcash = float(getcash[0]['cash'])
        if currentcash >= 250000:
            return apology("Cannot add more than 250000 in account")

        remainder = currentcash + cashadded
        db.execute("UPDATE users SET cash = ? WHERE id = ?", remainder, userid)
        currentprice = []
        totalshares = []
        totalvalue = []
        tickers = db.execute("SELECT DISTINCT symbol FROM portfolios WHERE userid = ?", userid)
        if not tickers:
            return apology("You have not bought or sold any stocks yet. Heres 10 grand click buy or get a quote.", 200)
        i = 0
        for row in tickers:
            stock = lookup(tickers[i]['symbol'])
            stockprice = stock.get("price")
            currentprice.append(stockprice)
            portfoliolist = db.execute("SELECT DISTINCT symbol FROM portfolios WHERE (userid = ?)", userid)
            amountbuy = db.execute("SELECT SUM(shares) FROM portfolios WHERE (symbol LIKE ? AND userid = ? AND action LIKE 'BUY')", tickers[i]['symbol'], userid)
            amountsold = db.execute("SELECT SUM(shares) FROM portfolios WHERE (symbol LIKE ? AND userid = ? AND action LIKE 'SELL')", tickers[i]['symbol'], userid)
            sharesleft = (int(amountbuy[0]['SUM(shares)'] or 0)- int(amountsold[0]['SUM(shares)'] or 0))
            totalshares.append(sharesleft)
            totalvalue.append(totalshares[i] * currentprice[i])
            i = i + 1
        totalvalues = float(sum(totalvalue))
        return render_template("index.html", user = db.execute("SELECT cash FROM users WHERE id = ?", userid), portfoliolist = portfoliolist, currentprice = currentprice, totalshares = totalshares, totalvalue = totalvalue,totalvalues=totalvalues)

    else:
        userid = session["user_id"]
        currentprice = []
        totalshares = []
        totalvalue = []
        tickers = db.execute("SELECT DISTINCT symbol FROM portfolios WHERE userid = ?", userid)
        if not tickers:
            return apology("You have not bought or sold any stocks yet. Heres 10 grand, click buy stocks or get a quote.", 200)
        i = 0
        for row in tickers:
            stock = lookup(tickers[i]['symbol'])
            stockprice = stock.get("price")
            currentprice.append(stockprice)
            amountbuy = db.execute("SELECT SUM(shares) FROM portfolios WHERE (symbol LIKE ? AND userid = ? AND action LIKE 'BUY')", tickers[i]['symbol'], userid)
            amountsold = db.execute("SELECT SUM(shares) FROM portfolios WHERE (symbol LIKE ? AND userid = ? AND action LIKE 'SELL')", tickers[i]['symbol'], userid)
            sharesleft = (int(amountbuy[0]['SUM(shares)'] or 0)- int(amountsold[0]['SUM(shares)'] or 0))
            portfoliolist = db.execute("SELECT DISTINCT symbol FROM portfolios WHERE userid = ?", userid)
            totalshares.append(sharesleft)
            totalvalue.append(totalshares[i] * currentprice[i])
            i = i + 1
        totalvalues = float(sum(totalvalue))
        return render_template("index.html", user = db.execute("SELECT cash FROM users WHERE id = ?", userid), portfoliolist = portfoliolist, currentprice = currentprice, totalshares = totalshares, totalvalue = totalvalue,totalvalues=totalvalues)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        userid = session["user_id"]
        getcash = db.execute("SELECT cash FROM users WHERE id = ?", userid)
        currentcash = float(getcash[0]['cash'])
        stock = lookup(request.form.get("symbol"))
        if stock == None:
            return apology("no stock with that ticker found", 400)
        try:
            cost = "{:.2f}".format(float(stock.get("price")) * int(request.form.get("shares")))
        except ValueError:
            return apology("shares cannot be fractional or strings.", 400)
        remainder = currentcash - float(cost)
        remainder = "{:.2f}".format(remainder)
        sharespurchased = request.form.get("shares")
        if currentcash <= float(cost):
            return apology("not enough cash to purchase shares", 400)
        if int(request.form.get("shares")) <= 0:
            return apology("shares cannot be negative or zero", 400)
        action = "BUY"
        db.execute("INSERT INTO portfolios (userid, symbol, shares, action, price_per_share, total_value_at_action, timestamp) VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)", userid, stock.get("symbol"), sharespurchased, action, stock.get("price"), cost)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", remainder, userid)
        return render_template("buy.html", sharespurchased = sharespurchased, cost = cost, remainder = remainder)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    userid = session["user_id"]
    return render_template("history.html", history = db.execute("SELECT * FROM portfolios WHERE userid = ?", userid))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        stockquote = lookup(request.form.get("symbol"))
        if stockquote == None:
            return apology("no stock with that ticker found", 400)
        return render_template("quote.html", name = stockquote.get("name"), price = "{:.2f}".format(stockquote.get("price")), symbol = stockquote.get("symbol"))
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password was submitted
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)

        # check that passwords match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords much match", 400)

        # check that username does not already exist
        elif db.execute("SELECT username FROM users WHERE username = ?", request.form.get("username")):
            return apology("username already exists, please choose a different username", 400)

        else:
            # hash the users password
            hashpw = generate_password_hash(request.form.get("password"))

            # Insert username and password into users
            db.execute("INSERT INTO users (username,hash) VALUES(?,?)", request.form.get("username"), hashpw)


        # Redirect user to home page
        return redirect("/login")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        i = 0
        found = 1
        userid = session["user_id"]
        stock = lookup(request.form.get("symbol"))
        found = db.execute("SELECT symbol FROM portfolios WHERE (symbol LIKE ? AND userid = ?)", stock.get("symbol"), userid)
        if len(found) < 1:
            return apology("you do not own that stock", 400)
        if float(request.form.get("shares")) <= 0:
            return apology("shares cannot be negative or zero", 400)
        amountbuy = db.execute("SELECT SUM(shares) FROM portfolios WHERE (symbol LIKE ? AND userid = ? AND action LIKE 'BUY')", stock.get("symbol"), userid)
        amountsold = db.execute("SELECT SUM(shares) FROM portfolios WHERE (symbol LIKE ? AND userid = ? AND action LIKE 'SELL')", stock.get("symbol"), userid)
        sharesleft = (int(amountbuy[0]['SUM(shares)'] or 0)-int(amountsold[0]['SUM(shares)'] or 0))
        if sharesleft < float(request.form.get("shares")):
            return apology("you do not have that many shares to sell")
        profit = float(stock.get("price")) * float(request.form.get("shares"))
        profit = "{:.2f}".format(profit)
        getcash = db.execute("SELECT cash FROM users WHERE id = ?", userid)
        currentcash = float(getcash[0]['cash'])
        remainder = float(currentcash) + float(profit)
        remainder = "{:.2f}".format(remainder)
        sharessold = request.form.get("shares")

        currentprice = []
        totalshares = []
        totalvalue = []
        stocks = []
        tickers = db.execute("SELECT DISTINCT symbol FROM portfolios WHERE userid = ?", userid)
        for row in tickers:
            stock = lookup(tickers[i]['symbol'])
            stockprice = stock.get("price")
            currentprice.append(stockprice)
            portfoliolist2 = db.execute("SELECT DISTINCT symbol FROM portfolios WHERE userid = ?", userid)
            amountbuy = db.execute("SELECT SUM(shares) FROM portfolios WHERE (symbol LIKE ? AND userid = ? AND action LIKE 'BUY')", tickers[i]['symbol'], userid)
            amountsold = db.execute("SELECT SUM(shares) FROM portfolios WHERE (symbol LIKE ? AND userid = ? AND action LIKE 'SELL')", tickers[i]['symbol'], userid)
            sharesleft = (int(amountbuy[0]['SUM(shares)'] or 0)- int(amountsold[0]['SUM(shares)'] or 0))
            totalshares.append(sharesleft)
            totalvalue.append(totalshares[i] * currentprice[i])
            i = i + 1
        action = "SELL"
        db.execute("INSERT INTO portfolios (userid, symbol, shares, action, price_per_share, total_value_at_action, timestamp) VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)", userid, request.form.get("symbol"), sharessold, action, stock.get("price"), profit)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", remainder, userid)
        return render_template("sell.html", portfoliolist2 = portfoliolist2, sharessold = sharessold, profit = profit, remainder = remainder, totalshares = totalshares)
    else:
        i = 0
        userid = session["user_id"]
        currentprice = []
        totalshares = []
        totalvalue = []
        stocks = []
        tickers = db.execute("SELECT DISTINCT symbol FROM portfolios WHERE userid = ?", userid)
        for row in tickers:
            stock = lookup(tickers[i]['symbol'])
            stockprice = stock.get("price")
            currentprice.append(stockprice)
            portfoliolist2 = db.execute("SELECT DISTINCT symbol FROM portfolios WHERE userid = ?", userid)
            stocks.append(portfoliolist2[i]['symbol'])
            amountbuy = db.execute("SELECT SUM(shares) FROM portfolios WHERE (symbol LIKE ? AND userid = ? AND action LIKE 'BUY')", tickers[i]['symbol'], userid)
            amountsold = db.execute("SELECT SUM(shares) FROM portfolios WHERE (symbol LIKE ? AND userid = ? AND action LIKE 'SELL')", tickers[i]['symbol'], userid)
            sharesleft = (int(amountbuy[0]['SUM(shares)'] or 0)- int(amountsold[0]['SUM(shares)'] or 0))
            totalshares.append(sharesleft)
            totalvalue.append(totalshares[i] * currentprice[i])
            i = i + 1
        return render_template("sell.html", portfoliolist2 = portfoliolist2, totalshares = totalshares)
