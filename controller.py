from flask import render_template, session, request, redirect, flash
from app import *
from model import *
from sqlalchemy import or_, func, desc

#Workings:
#Redirect(): sends an HTTP redirect response to client
#instruct the client to make a GET request to specified url

#methods=["POST"]: Checks if request method is POST request (form submission)


#ROUTE FOR HOME PAGE
@app.route("/")
def index():
    #Check if "user_id" key exists in session
    if "user_id" in session: 
        #Query all products from the database
        products=Product.query.all()
        #Create a list of product details as tuples and sort in order by ID
        sorted_products = [(product.id, product.name, product.brand, product.category, product.mfg_date, product.exp_date, product.unit, product.qty, product.price_per_unit, product.image) for product in products]
        sorted_products.sort(reverse = True)
        print(sorted_products)
        #Create a dictionary to group products by category
        home_category_products = dict()
        for product in products:
            #Query the category associated with the product
            category = Category.query.filter_by(id=product.category).first()
            #Append product details to the list under the appropriate category key
            if category.name in home_category_products:
                home_category_products[category.name] += [(product.id, product.name, product.brand, product.category, product.mfg_date, product.exp_date, product.unit, product.qty, product.price_per_unit, product.image)]
            else:
                home_category_products[category.name] = [(product.id, product.name, product.brand, product.category, product.mfg_date, product.exp_date, product.unit, product.qty, product.price_per_unit, product.image)]
        #Render template "index.html" with relevant variables
        return render_template("index.html", flag=False, recent_products = sorted_products[:8], dict_of_all_category_products = home_category_products)
    else:
        #If user is not logged in, redirect to the sign-in page
        return redirect("/sign-in")
    

#ROUTE FOR SIGN-IN PAGE
@app.route("/sign-in")
def sign_in(): 
    #Check if "user_id" key exists in session
    if "user_id" in session:
        #retrieve the user_id from session & store it in variable
        userid = session["user_id"]
        return render_template("index.html", flag=False)
    #If user is not logged in, render the "sign-in.html" template
    return render_template("sign-in.html", flag=False)


#ROUTE FOR SIGN-UP PAGE
@app.route("/sign-up")
def sign_up():
    return render_template("sign-up.html", flag=False)


#ROUTE FOR HANDLING LOGIN AUTHENTICATION
@app.route("/login_authentication", methods=["POST"])             #
def login():
    #Check if request method is POST request (form submission)
    if(request.method=="POST"):
        #Get value of "email" & "password" from the form submitted by user
        cemail = request.form.get("email")
        cpassword = request.form.get("password")
        #Query the database to check if a user with the provided email & password exists
        user = User.query.filter_by(email=cemail, password=cpassword)
        #Convert the result of the query into list
        check = [i for i in user]
        #In there is atleast 1 user in the check list whose "email" & "password" match a user in the database
        if check:
            #Store that user ID in the session as "user_id" key
            session["user_id"] = check[0].id
            print(session["user_id"])
            print("authentication done")
            #redirect to home page after successful login
            return redirect("/")
        else:
            #If provided email & password not match with any user in the database
            print("not found")
            flash("INVALID EMAIL OR PASSWORD")
            #redirect user to sign_in page to try again
            return redirect("/sign-in")
    else:
        #If request method is not POST request (i.e., GET request)
        return "bad request"
    

#ROUTE FOR HANDLING USER LOGOUT
@app.route("/logout", methods=["POST"])
def logout():
    #If request method is POST request
    if(request.method=="POST"):
        #Remove the "user_id" key from the session
        session.pop("user_id")
        print("logout")
        #redirect to sign-in page after succesful logout
        return redirect("sign-in")
    #If request method is NOT POST request
    else:
        #Check if user_id key exists in session i.e., logged in
        if("user_id" in session):
            return redirect("/")
        ##Check if user_id key NOT exists in session i.e., logged out
        else:
            return redirect("/sign-in")


#ROUTE FOR REGISTERING A NEW USER
@app.route('/register', methods=["POST"])
def register():
    #If request method is POST request
    if(request.method == "POST"):
        try:
            #Get user details from submitted form
            cname = request.form.get("name")
            caddress = request.form.get("address")
            ccontact = request.form.get("contact_no")
            cemail = request.form.get("email")
            cpassword = request.form.get("password")
            csex = request.form.getlist("sex")
            #Loop through the list of "sex" to get 1st element 
            for i in csex[:1]:
                #Create new User object with the provided details 
                #Then, add the new user to the database session for insertion
                update_user_db = User(name=cname, address=caddress, contact_no=ccontact, email=cemail, password=cpassword, sex=i)
            db.session.add(update_user_db)
            db.session.flush()
        except Exception as e:
            #If an exception occurs suring registration process, roll the session (undo changes)
            print("rollback")
            db.session.rollback()
            #return exception message & "Not Registered" message as a tuple
            return "{}".format(e),"Not Registered"
        else:
            #If there is no exception, commit the changes to the database session (i.e., perform the registration)
            db.session.commit()
            #Query the database to retrieve the newly registered user using the provided email & password
            user = User.query.filter_by(email=cemail, password=cpassword)
            check = [i for i in user]
            if check:
                #If user exists, store the userID in the session as "user_id" key
                session["user_id"] = check[0].id
                #Redirect the user to home page after successful registration & login
                return redirect("/")


#ROUTE FOR DISPLAYING CATEGORIES
@app.route("/category")
def category():
    #Check if "user_id" key exists in session (i.e., logged in)
    if "user_id" in session:
        #Query all categories from the database
        category = Category.query.all()
        #Convert query result to a list
        check = [i for i in category]
        #Render category.html template & pass the list of all categories (check)
        return render_template("category.html", all_categories = check, flag=False)
    else:
        #If "user_id" key not exists in session (i.e., not logged in)
        #redirect user to sign-in page to authenticate before accessing the categories
        return redirect("/sign-in")
    

#ROUTE FOR DISPLAYING PRODUCTS UNDER A SPECIFIC CATEGORY
@app.route("/product/<int:i>")
def product(i):
    #Check if "user_id" key exists in session
    if "user_id" in session:
        #Query all products that belongs to specified category 
        product = Product.query.filter_by(category=i)
        #Convert the query result into list
        check = [i for i in product]
        #Render product.html template & pass the list of all products in specified category
        return render_template("product.html", all_products = check, flag=False)
    else:
        #If "user_id" key not exists in the session
        #redirect the user to sign-in page to authenticate before accessing the products
        return redirect("/sign-in")
    

#ROUTE FOR DISPLAYING USER CART
@app.route("/cart")
def cart():
    #Check if "user_id" key exists in the session
    if "user_id" in session:
        #Query the user cart items from the database based on their user_id
        cart = Cart.query.filter_by(user_id=session["user_id"])
        #Convert the query result into list
        cart_list = [i for i in cart]
        #Create empty list to store product details in the cart 
        pro_list = []
        #Initailize the total_price of the items in the cart 
        total_price = 0
        #Loop through each item in the cart list to get the product_details
        for item in cart_list:
            #Query the product details based on product_id stored in the cart
            pro = Product.query.filter_by(id=item.product_id).first()
            #Append product details to the pro_list
            pro_list.append((pro.name, item.product_qty, pro.price_per_unit, pro.category, pro.image, pro.brand, int(pro.price_per_unit)*int(item.product_qty), item.cart_id ))
            print(pro.name, item.product_qty, pro.price_per_unit, pro.category, pro.image, pro.brand)
        #Calaculate the total price of all items in the cart by adding up of individual prices
        for price in pro_list:
            total_price += int(price[6])
        #Render cart.html template & pass the product_list (pro_list) containing product details in the cart & cart_total containing total_price
        return render_template("cart.html", product_list = pro_list , flag=False, cart_total=total_price)
    else:
        #If "user_id" key not exists in the session
        #redircet to sign-in page to authenticate before accessing their cart
        return redirect("/sign-in")
    

#ROUTE FOR REMOVING AN ITEM FROM USER CART
@app.route("/remove_from_cart/<int:id>")
def remove_from_cart(id):
    #Check if "user_id" exists in session
    if "user_id" in session:
        #Query the cart items from the database based on cart_id & user_id
        #cart_id is extracted from url as "id" parameter
        #cart_id & user_id are used to uniquely identify the cart item for deletion
        Cart.query.filter_by(user_id=session["user_id"], cart_id=id).delete()
        #Flush changes to database session
        db.session.flush()
        #Commit changes to database
        db.session.commit()
        #Redirect user to their cart page after successful removal of cart item
        return redirect("/cart")
    else:
        #If "user_id" key not exists
        #redirect user to sign-in page to authenticate before performing any cart-related actions
        return redirect("/sign-in")


#ROUTE FOR ADDING AN ITEM TO USER CART
@app.route("/add_to_cart/<int:id>", methods=["POST"])
def add_to_cart(id):
    #Check if "user_id" key exists in the session
    if "user_id" in session:
        #Query the product with the given "id" from the database
        prod=Product.query.filter_by(id=id).first()
        #Query the user cart to check if the product is already in cart based on its "id"
        cart = Cart.query.filter_by(user_id=session["user_id"], product_id=id).first()
        #Get qty of the product to be added to cart from submitted form
        qty = request.form.get("quantity")
        if (cart):
            #If product is already in cart, update its qty by adding new qty
            cart.product_qty += int(qty)
            #Flush changes to database
            db.session.flush()
            #Commit changes to database
            db.session.commit()
            #Redirect user back to product page after adding product to cart
            return redirect(f"/product/{prod.category}")
        else:
            #If product is not already in cart, create a new cart item with product details
            new_cart_item=Cart(user_id=session["user_id"], product_id=id, product_qty=qty)
            #Add new cart item to the database session
            db.session.add(new_cart_item)
            #Commit changes to database
            db.session.commit()
            #Redirect user back to the product page after adding product to cart
            return redirect(f"/product/{prod.category}")
    else:
        #If "user_id" key not exists in session
        #redirect user to sign-in page to authenticate before performing any cart-related actions
        return redirect("/sign-in")
             

#ROUTE HANDLER FOR SEARCH
@app.route("/search")
def search():
    #request.arg.get() is used to retrieve query parameters from the URL
    #Query parameters added to the URL after "?" symbol & used for GET requests
    input_query = request.args.get("query")
    if input_query:
        #Check if input query matches any category name
        category_results = Category.query.filter(Category.name.ilike(f"%{input_query}%")).all()

        if category_results:
            #If there are category matches, display products under the first matched category
            category_id = category_results[0].id
            products_in_category = Product.query.filter_by(category=category_id).all()
            return render_template("search.html", query=input_query, results=products_in_category, flag=False)

        #If no category matches, search for products matching the input query
        #"db.or_" used to create a SQL "OR" condition when querying a database
        #"ilike" operator is used to match a pattern in a case-insensitive manner.
        #"f-string" is used to construct the pattern for the "LIKE" query
        product_results = Product.query.filter(
            db.or_(
                Product.name.ilike(f"%{input_query}%"),
                Product.brand.ilike(f"%{input_query}%"),
            )
        ).all()

        if product_results:
            return render_template("search.html", query=input_query, results=product_results, flag=False)
    #If there is no input query, render the "search.html" template with no results
    return render_template("search.html", query=input_query, results=None, flag=False)


#ROUTE FOR ADDING AN ITEM TO USER CART BASED ON SEARCH QUERY
@app.route("/add_to_cart_search/<int:id>", methods=["POST", "GET"])
def add_to_cart_search(id):    
    #Check if "user_id" key exists in the session
    if "user_id" in session:
        input_query = request.form.get("query")
        #Query the product with the given "id" from the database
        prod=Product.query.filter_by(id=id).first()
        #Query the user cart to check if the product is already in cart based on its "id"
        cart = Cart.query.filter_by(user_id=session["user_id"], product_id=id).first()
        #Get qty of the product to be added to cart from submitted form
        qty = request.form.get("quantity")
        if (cart):
            #If product is already in cart, update its qty by adding new qty
            cart.product_qty += int(qty)
            #Flush changes to database
            db.session.flush()
            #Commit changes to database
            db.session.commit()
            if input_query:
            #Check if input query matches any category name
                category_results = Category.query.filter(Category.name.ilike(f"%{input_query}%")).all()

                if category_results:
                    #If there are category matches, display products under the first matched category
                    category_id = category_results[0].id
                    products_in_category = Product.query.filter_by(category=category_id).all()
                    return render_template("search.html", query=input_query, results=products_in_category, flag=False)

                #If no category matches, search for products matching the input query
                product_results = Product.query.filter(
                    db.or_(
                        Product.name.ilike(f"%{input_query}%"),
                        Product.brand.ilike(f"%{input_query}%"),
                    )
                ).all()

                if product_results:
                    return render_template("search.html", query=input_query, results=product_results, flag=False)

            return render_template("search.html", query=input_query, results=None, flag=False)
        else:
            #If product is not already in cart, create a new cart item with product details
            new_cart_item=Cart(user_id=session["user_id"], product_id=id, product_qty=qty)
            #Add new cart item to the database session
            db.session.add(new_cart_item)
            #Commit changes to database
            db.session.commit()
            if input_query:
                #Check if input query matches any category name
                category_results = Category.query.filter(Category.name.ilike(f"%{input_query}%")).all()

                if category_results:
                    #If there are category matches, display products under the first matched category
                    category_id = category_results[0].id
                    products_in_category = Product.query.filter_by(category=category_id).all()
                    return render_template("search.html", query=input_query, results=products_in_category, flag=False)

                #If no category matches, search for products matching the input query
                product_results = Product.query.filter(
                    db.or_(
                        Product.name.ilike(f"%{input_query}%"),
                        Product.brand.ilike(f"%{input_query}%"),
                    )
                ).all()

                if product_results:
                    return render_template("search.html", query=input_query, results=product_results, flag=False)

            return render_template("search.html", query=input_query, results=None, flag=False)
    else:
        #If "user_id" key not exists in session
        #redirect user to sign-in page to authenticate before performing any cart-related actions
        return redirect("/sign-in")
             
      
#ROUTE FOR ADDING AN ITEM TO USER CART FROM HOME PAGE
@app.route("/add_to_cart_to_home/<int:id>", methods=["POST"])
def add_to_cart_to_home(id):
    #Check if "user_id" key exists in the session
    if "user_id" in session:
        #Query the product with the given "id" from the database
        prod=Product.query.filter_by(id=id).first()
        #Query the user cart to check if the product is already in cart based on its "id"
        cart = Cart.query.filter_by(user_id=session["user_id"], product_id=id).first()
        #Get qty of the product to be added to cart from submitted form
        qty = request.form.get("quantity")
        #This ID is used to create a redirect link back to the product page after adding the product to the cart.
        htmlid=request.form.get("htmlid")
        if (cart):
            #If product is already in cart, update its qty by adding new qty
            cart.product_qty += int(qty)
            #Flush changes to database
            db.session.flush()
            #Commit changes to database
            db.session.commit()
            #Redirect user back to product page after adding product to cart
            return redirect(f"/#{htmlid}")
        else:
            #If product is not already in cart, create a new cart item with product details
            new_cart_item=Cart(user_id=session["user_id"], product_id=id, product_qty=qty)
            #Add new cart item to the database session
            db.session.add(new_cart_item)
            #Commit changes to database
            db.session.commit()
            #Redirect user back to the product page after adding product to cart
            return redirect(f"/#{htmlid}")
    else:
        #If "user_id" key not exists in session
        #redirect user to sign-in page to authenticate before performing any cart-related actions
        return redirect("/sign-in")
            

#ROUTE FOR DISPLAYING USER ORDERS
@app.route("/order")
def order():
    #Check if "user_id" key exists in session
    if "user_id" in session:
        #Query the Order table to retrieve all orders associated with the user
        all_orders = Order.query.filter_by(user_id=session["user_id"])
        #Create a list to store details of all orders
        list_of_all_orders = [detail for detail in all_orders]
        #Render the "order.html" template and pass the list of orders to the template
        return render_template("order.html", all_orders=list_of_all_orders)
    else:
        #If user is not authenticated, redirect to the sign-in page
        return redirect("/sign-in")
    

#ROUTE FOR HANDLING ORDERS
@app.route("/order_details/<int:id>")
def order_details(id):
    #Query the Order_details table to retrieve details of the specified order
    orders = Order_details.query.filter_by(order_id=id)
    #Query the Order table to retrieve information about the specified order
    for_price = Order.query.filter_by(id=id).first()
    #Create empty lists to store order details and products that are out of stock
    order_detail = []
    check_for_out_of_stock = []
    #Get the total price of the order from the Order table
    total_price = for_price.order_total
    #Iterate through each order detail
    for order in orders:
        #Query the Product table to get information about the product in the order detail
        product = Product.query.filter_by(id=order.product_id).first()
        #Check if the product is out of stock (qty <= 0)
        if product.qty <= 0:
            check_for_out_of_stock.append(product.name)
        #Append details of the product and order to the order_detail list
        order_detail.append((product.name, order.product_qty, product.price_per_unit, product.category, product.image, product.brand, int(product.price_per_unit)*int(order.product_qty), order.order_id))
    #If there are products out of stock, display a flash message
    if check_for_out_of_stock:
        flash(f"These products are Out-of-Stock {check_for_out_of_stock} ! Will back to you soon...")
    #Render the "order_details.html" template and pass relevant data to the template
    return render_template("order_details.html", product_list=order_detail, total_price=total_price, order_id=id)


#ROUTE FOR PROMOCODE
@app.route("/promocode")
def promocode():
    if "user_id" in session:
        #Retrieve the "promocode" parameter from the URL query string
        offer = request.args.get("promocode")
        #Check if the promocode is "IIT10"
        if offer == "IIT10":
            #Query the user cart items from the database based on their user_id
            cart = Cart.query.filter_by(user_id=session["user_id"])
            #Convert the query result into list
            cart_list = [i for i in cart]
            #Create empty list to store product details in the cart 
            pro_list = []
            #Initailize the total_price of the items in the cart 
            total_price = 0
            #Loop through each item in the cart list to get the product_details
            for item in cart_list:
                #Query the product details based on product_id stored in the cart
                pro = Product.query.filter_by(id=item.product_id).first()
                #Append product details to the pro_list
                pro_list.append((pro.name, item.product_qty, pro.price_per_unit, pro.category, pro.image, pro.brand, int(pro.price_per_unit)*int(item.product_qty), item.cart_id ))
                print(pro.name, item.product_qty, pro.price_per_unit, pro.category, pro.image, pro.brand)
            #Calaculate the total price of all items in the cart by adding up of individual prices
            for price in pro_list:
                total_price += int(price[6])
            #Apply a 10% discount to the total price:
            total_price = total_price - int(total_price * 0.1)
            #Ensure that the total price is not negative
            total_price = 0 if total_price < 0 else total_price
            flash("IIT10 applied... 10% Off")
            #Render cart.html template & pass the product_list (pro_list) containing product details in the cart & cart_total containing total_price
            return render_template("cart.html", product_list = pro_list , flag=False, cart_total=total_price)
        elif offer == "IIT500":
            #Query the user cart items from the database based on their user_id
            cart = Cart.query.filter_by(user_id=session["user_id"])
            #Convert the query result into list
            cart_list = [i for i in cart]
            #Create empty list to store product details in the cart 
            pro_list = []
            #Initailize the total_price of the items in the cart 
            total_price = 0
            #Loop through each item in the cart list to get the product_details
            for item in cart_list:
                #Query the product details based on product_id stored in the cart
                pro = Product.query.filter_by(id=item.product_id).first()
                #Append product details to the pro_list
                pro_list.append((pro.name, item.product_qty, pro.price_per_unit, pro.category, pro.image, pro.brand, int(pro.price_per_unit)*int(item.product_qty), item.cart_id ))
                print(pro.name, item.product_qty, pro.price_per_unit, pro.category, pro.image, pro.brand)
            #Calaculate the total price of all items in the cart by adding up of individual prices
            for price in pro_list:
                total_price += int(price[6])
            #Apply flat 500 off discount to the total price
            total_price = total_price - 500
            #Ensure that the total price is not negative
            total_price = 0 if total_price < 0 else total_price
            flash("IIT500 applied... 500 Off")
            #Render cart.html template & pass the product_list (pro_list) containing product details in the cart & cart_total containing total_price
            return render_template("cart.html", product_list = pro_list , flag=False, cart_total=total_price)
        else:
            #Query the user cart items from the database based on their user_id
            cart = Cart.query.filter_by(user_id=session["user_id"])
            #Convert the query result into list
            cart_list = [i for i in cart]
            #Create empty list to store product details in the cart 
            pro_list = []
            #Initailize the total_price of the items in the cart 
            total_price = 0
            #Loop through each item in the cart list to get the product_details
            for item in cart_list:
                #Query the product details based on product_id stored in the cart
                pro = Product.query.filter_by(id=item.product_id).first()
                #Append product details to the pro_list
                pro_list.append((pro.name, item.product_qty, pro.price_per_unit, pro.category, pro.image, pro.brand, int(pro.price_per_unit)*int(item.product_qty), item.cart_id ))
                print(pro.name, item.product_qty, pro.price_per_unit, pro.category, pro.image, pro.brand)
            #Calaculate the total price of all items in the cart by adding up of individual prices
            for price in pro_list:
                total_price += int(price[6])
            flash("Wrong Promocode...")
            #Render cart.html template & pass the product_list (pro_list) containing product details in the cart & cart_total containing total_price
            return render_template("cart.html", product_list = pro_list , flag=False, cart_total=total_price)
    else:
        return redirect("/sign-in")
            

#ROUTE FOR CREATING A NEW ORDER
@app.route("/create_order")
def create_order():
    #Check if "user_id" exists in the session
    if "user_id" in session:
        #Get the total price of the order from the query parameters
        # Get checkout total
        total = float(request.args.get("total_price"))

        ###############
        # # Release 1: Apply 5% discount for orders over $50
        if total > 50:
            # # Release 2: Apply 10% discount for orders over $50
            discount = total * 0.10
            total = round(total - discount, 2)
        #Create a new Order record with the user's ID and the total price
        new_order = Order(user_id=session["user_id"], order_total=total)
        db.session.add(new_order)
        #we use flush bcoz of it, we can use of order_id in order_detail table. This way if we'll face any error, the above entries won't be permanent
        #To ensure that the new order is created and has an order_id.
        db.session.flush()
        #Query the user's cart items
        cart = Cart.query.filter_by(user_id=session["user_id"])
        #Query the newly created order using get_order_detail.
        get_order_detail = Order.query.filter_by(user_id=session["user_id"], order_total=total).order_by(desc(Order.order_time)).first()
        #For each item in the cart, retrieve the corresponding product details
        for order in cart:
            product_detail = Product.query.filter_by(id=order.product_id).first()
            #Create a new Order_details record with the order ID, user ID, product ID, product quantity, and calculated price
            update_order_detail = Order_details(order_id=get_order_detail.id, user_id=session["user_id"], product_id=order.product_id, product_qty=order.product_qty, price=(int(product_detail.price_per_unit)*int(order.product_qty)))
            db.session.add(update_order_detail)
            #Update the product quantity by subtracting the ordered quantity
            product_detail.qty-=order.product_qty
            #To apply the changes and ensure the order_id is available for the order details
            db.session.flush()
        #Delete the cart items for the user
        Cart.query.filter_by(user_id=session["user_id"]).delete()
        #Commit the changes to the database
        db.session.commit()
        flash("Order placed successfully...Will reach you soon!")
        #Redirect the user to the order details page for the newly created order
        return redirect(f"/order_details/{get_order_detail.id}")
    else:
        return redirect("/sign-in")
