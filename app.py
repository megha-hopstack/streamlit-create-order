import streamlit as st
import os
from openai import OpenAI
from pymongo import MongoClient
import json
from bson import ObjectId
import requests
import time

def get_completion(prompt, client_instance, model="gpt-3.5-turbo-1106"):
    messages = [{"role": "user", "content": prompt}]
    response = client_instance.chat.completions.create(
    model=model,
    messages=messages,
    max_tokens=500,
    temperature=0,
    )
    return response.choices[0].message.content

def get_completion_json(prompt, client_instance, model="gpt-3.5-turbo-1106"):
    messages = [{"role": "user", "content": prompt}]
    response = client_instance.chat.completions.create(
    model=model,
    messages=messages,
    max_tokens=300,
    response_format={ "type": "json_object" },
    temperature=1,
    )
    return response.choices[0].message.content

# Function to connect to database
def database_connection(mongo_url):
    uat = MongoClient(mongo_url)
    database = uat["platform-uat"]
    return database

# Function to display the initial greeting and options
def display_greeting():
    st.title("Welcome to Our Chat Assistant")
    st.write("What would you like to do today? Here are some things I can help you with:")

    # Create three columns for the options
    col1, col2, col3 = st.columns(3)

    # Display each option in its own box within a column
    with col1:
        st.container()
        st.write("📦 Create Order")

    with col2:
        st.container()
        st.write("📝 Create Product Listing")

    with col3:
        st.container()
        st.write("🚚 Create Shipment Plan")

    st.write("Please type your request below.")

# Function to check for missing mandatory fields using OpenAI
def check_mandatory_fields(user_input, client):
    mandatory_fields = [
        "Warehouse Name/Code",
        "Customer Name/Code",
        "Product SKU",
        "Quantity"
    ]
    mandatory_fields_str = ", ".join([f"'{field}'" for field in mandatory_fields])


    prompt = f"""
    The user's input is: "{user_input}"
    The mandatory fields are: {mandatory_fields_str}.

    Check if all the mandatory fields are present in the user's input. \
    The name of the fields need not exactly match the user's input. Use your discretion to understand if the given fields and user's inputs match.\
    If any fields are missing, list them. Do not add the fields to this list if they exist in the user input.\
    If all fields are present, respond with "All mandatory fields are present".
    Do not response with anything other than either the missing fields list or "All mandatory fields are present".
    """

    response = get_completion(prompt, client)
    return response

#Function to return json from user input
def json_from_user_input(user_input, client):
    mandatory_fields = [
        "Warehouse Name/Code",
        "Customer Name/Code",
        "Product SKU",
        "Quantity"
    ]
    optional_fields = [
        "Order Date",
        "Order ID",
        "Carrier",
        "Form Factor",
        "Insurance Required",
        "Product Lot/Batch ID",
        "Shipping Address (name)",
        "Shipping Address (email)",
        "Shipping Address (phone)",
        "Shipping Address (line1)",
        "Shipping Address (line2)",
        "Shipping Address (city)",
        "Shipping Address (state)",
        "Shipping Address (country)",
        "Shipping Address (zip)",
        "Validate Address"
    ]

    prompt = f"""
    The user's input is: "{user_input}"
    The mandatory fields are: {mandatory_fields}.
    The optional fields are: {optional_fields}.

    Return a JSON object where keys are all the fields in {mandatory_fields} and {optional_fields}. Extract the respective values from the user input.
    For example: if user writes warehouse 554, then the dictionary should contain key as "Warehouse Name/Code" and value as "554".
    The name of the fields need not exactly match the user's input. Use your discretion to understand which part of the user's input refers to which key.
    For insurance required or validate address the key should be 'yes', 'no' or left blank if not input by user.
    For any optional field leave the value blank if it is not input by the user, but do not leave the keys blank.
    """

    response = get_completion_json(prompt, client)
    response_dict = json.loads(response)  # Convert the JSON string to a Python dictionary
    return response_dict

def validate_warehouse(warehouse_code, database):
    results = database.warehouses.find({"$or": [{"name": warehouse_code}, {"code": warehouse_code}]}, {"_id": 1})
    warehouse_ids = [str(result['_id']) for result in results]
    if warehouse_ids:
        return warehouse_ids
    return "Warehouse name/code not valid"

def validate_customer(customer_code, database):
    results = database.customers.find({"$or": [{"name": customer_code}, {"code": customer_code}]}, {"_id": 1})
    customer_ids = [str(result['_id']) for result in results]
    if customer_ids:
        return customer_ids
    return "Customer name/code not valid"


def validate_order_date(order_date, client):
    prompt = f""" Is {order_date} a valid date? If not, respond with "Date not valid".
    If yes, convert it to epoch time and return the epoch time only. Assume the timezone is UTC.
    Do not respond with anything other than either the epoch time or "Date not valid".
    """
    response = get_completion(prompt, client)
    return response

def validate_quantity(quantity, client):
    prompt = f"""Is '{quantity}' a valid positive number or a word representing a positive number? If not, respond with "Quantity not valid".
            If it is an integer, simply return that. If it is a word representing a positive number, return the integer it respresents. Don't respond with anything else."""
    response = get_completion(prompt, client)
    return int(response)

def validate_product_sku(warehouses, customers, sku, database):
    # Find the product variant that matches the SKU and any of the given warehouses and customers
    result = database.productvariants.find_one(
        {"warehouse": {"$in": warehouses}, "customer": {"$in": customers}, "sku": sku},
        {"_id": 1, "warehouse": 1, "customer": 1}
    )
    print(result)
    if result:
        # Return the matched SKU ID, warehouse ID, and customer ID
        return str(result['_id']), result['warehouse'], result['customer']
    return "SKU not valid", None, None


def validate_form_factor(form_factor):
    valid_form_factors = ["each", "case", "carton", "pallet"]
    if not form_factor:  # Checks for None or empty string
        return "Each"
    elif isinstance(form_factor, str) and form_factor.lower() in valid_form_factors:
        return form_factor.capitalize()
    else:
        return "Form factor not valid"


def validate_insurance_required(insurance_required):
    if not insurance_required:  # Checks for None or empty string
        return False
    elif isinstance(insurance_required, str) and insurance_required.lower() in ("yes", "no"):
        return insurance_required.lower() == "yes"
    else:
        return "Insurance required not valid"

def validate_address(validate_address):
    if not validate_address:  # Checks for None or empty string
        return False
    elif isinstance(validate_address, str) and validate_address.lower() in ("yes", "no"):
        return validate_address.lower() == "yes"
    else:
        return "Validate address not valid"


def validate_carrier(carrier):
    valid_carriers = {"ups": "UPS", "usps": "USPS", "fedex": "FedEx"}
    if not carrier:  # Checks for None or empty string
        return ""
    elif isinstance(carrier, str) and carrier.lower() in valid_carriers:
        return valid_carriers[carrier.lower()]
    else:
        return "Carrier not valid"


def validate_fields(order, client, mongo_url):
    database = database_connection(mongo_url)
    validated_order = order.copy()


    # Validate warehouse
    warehouse_ids = validate_warehouse(order["Warehouse Name/Code"], database)
    if warehouse_ids == "Warehouse name/code not valid":
        return warehouse_ids, None

    # Validate customer
    customer_ids = validate_customer(order["Customer Name/Code"], database)
    if customer_ids == "Customer name/code not valid":
        return customer_ids, None

    # Validate order date
    order_date = order.get("Order Date", "")
    if order_date:
        order_date_epoch = validate_order_date(order_date, client)
        if order_date_epoch == "Date not valid":
            return order_date_epoch, None
        validated_order["Order Date"] = order_date_epoch * 1000
    else:
        validated_order["Order Date"] = int(time.time()) * 1000

    # Validate quantity
    quantity = validate_quantity(order["Quantity"], client)
    if quantity == "Quantity not valid":
        return quantity, None
    validated_order["Quantity"] = quantity

    # Validate product SKU
    sku_id, matched_warehouse_id, matched_customer_id = validate_product_sku(warehouse_ids, customer_ids, order["Product SKU"], database)
    if sku_id == "SKU not valid":
        return sku_id, None

    validated_order["Warehouse ID"] = matched_warehouse_id
    validated_order["Customer ID"] = matched_customer_id
    validated_order["Product SKU ID"] = sku_id

    # Validate form factor
    form_factor = validate_form_factor(order.get("Form Factor"))
    if form_factor == "Form factor not valid":
        return form_factor, None
    validated_order["Form Factor"] = form_factor

    # Validate carrier
    carrier = validate_carrier(order.get("Carrier"))
    if carrier == "Carrier not valid":
        return carrier, None
    validated_order["Carrier"] = carrier

    # Validate insurance required
    insurance_required = validate_insurance_required(order.get("Insurance Required"))
    if insurance_required == "Insurance required not valid":
        return insurance_required, None
    validated_order["Insurance Required"] = insurance_required

    # Validate address
    validate_address_result = validate_address(order.get("Validate Address"))
    if validate_address_result == "Validate address not valid":
        return validate_address_result, None

    validated_order["Validate Address"] = validate_address_result
    return "Yes", validated_order


def create_order_data(validated_order, client, mongo_url):
    database = database_connection(mongo_url)
    sku_id = validated_order["Product SKU ID"]

    # Query the productvariants collection
    product_variant = database.productvariants.find_one(
        {"_id": ObjectId(sku_id)},
        {"productId": 1, "sku": 1, "attributes": 1, "marketplaceAttributes": 1, "fnSku": 1, "name": 1}
    ) or {}



    # Query the skubinmappings collection
    sku_bin_mapping = database.skubinmappings.find_one(
        {"product": ObjectId(sku_id)},
        {"formFactor": 1, "nestedFormFactor": 1, "lotId": 1}
    ) or {}

    try:
        form_factor = validated_order.get("formFactor")
    except:
        form_factor = sku_bin_mapping.get("formFactor", "")

    order_data = {
        "warehouse": validated_order["Warehouse ID"],
        "customer": validated_order["Customer ID"],
        "warehouseToBeSelected": True,
        "customerToBeSelected": True,
        "toValidAddress": validated_order.get("Validate Address"),
        "orderId": validated_order.get("Order ID"),
        "orderLineItems": [
            {
                "productId": product_variant.get("productId", ""),
                "formFactor": form_factor,
                "quantity": validated_order["Quantity"],
                "lotId": sku_bin_mapping.get("lotId", ""),
                "nestedFormFactorId": sku_bin_mapping.get("nestedFormFactor", ""),
                "marketplaceAttributes": product_variant.get("marketplaceAttributes", ""),
                "attributes": product_variant.get("attributes", ""),
                "fnSku": product_variant.get("fnSku", ""),
                "sku": product_variant.get("sku"),
                "name": product_variant.get("name", "")
            }
        ],
        "shippingAddress": {
            "name": validated_order.get("Shipping Address (name)"),
            "email": validated_order.get("Shipping Address (email)"),
            "phone": validated_order.get("Shipping Address (phone)"),
            "line1": validated_order.get("Shipping Address (line1)"),
            "line2": validated_order.get("Shipping Address (line2)"),
            "city": validated_order.get("Shipping Address (city)"),
            "state": validated_order.get("Shipping Address (state)"),
            "country": validated_order.get("Shipping Address (country)"),
            "zip": validated_order.get("Shipping Address (zip)")
        },
        "carrier": validated_order.get("Carrier"),
        "insuranceRequired": validated_order.get("Insurance Required"),
        "orderDate": validated_order.get("Order Date"),  # Current time in milliseconds
        "orderType": "Hopstack"
    }

    return order_data

def login(url, username, password, logout_all=True):
    headers = {'Content-Type': 'application/json',
              'tenant': '{"id":"62cdb0ac6227b7ed224d79aa","name":"Hopstack Inc","subdomain":"hst","code":"hst", "active": true}'
    }
    query = """
    mutation login($username: String!, $password: String!, $logoutAll: Boolean) {
        login(username: $username, password: $password, logoutAll: $logoutAll) {
            token
        }
    }
    """
    variables = {
        "username": username,
        "password": password,
        "logoutAll": logout_all,
    }
    response = requests.post(url, json={'query': query, 'variables': variables}, headers=headers)
    data = response.json()
    print(data)
    return data.get('data', {}).get('login', {}).get('token')

def save_order(url, token, order_data):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}',
        'tenant': '{"id":"62cdb0ac6227b7ed224d79aa","name":"Hopstack Inc","subdomain":"hst","code":"hst", "active": true}'
    }
    query = """
     mutation saveOrder(
    $trackingNumber: String
    $orderLineItems: [OrderLineItemInput]
    $customer: ID
    $warehouse: ID
    $orderId: String
    $id: ID
    $carrier: String
    $orderDate: Date
    $workflowType: String
    $shippingAddress: ShippingAddressInput
    $orderType: String
    $carrierService: String
    $insuranceRequired: Boolean
    $insuranceProvider: String
    $insuredValue: Float
    $toValidAddress: Boolean
    $preSelectedCarrierRate: SelectedCarrierRateInput
    $typeOfShipment: String
    $estimatedBoxes: [OrderEstimatedBoxInput]
  ) {
    saveOrder(
      orderInput: {
        trackingNumber: $trackingNumber
        orderLineItems: $orderLineItems
        customer: $customer
        warehouse: $warehouse
        orderId: $orderId
        id: $id
        carrier: $carrier
        orderDate: $orderDate
        workflowType: $workflowType
        shippingAddress: $shippingAddress
        orderType: $orderType
        carrierService: $carrierService
        insuranceRequired: $insuranceRequired
        insuranceProvider: $insuranceProvider
        insuredValue: $insuredValue
        toValidAddress: $toValidAddress
        preSelectedCarrierRate: $preSelectedCarrierRate
        typeOfShipment: $typeOfShipment
        estimatedBoxes: $estimatedBoxes
      }
    ) {
      message
    }
  }
    """
    variables = order_data  # The order_data should be a dictionary formatted as the GraphQL variables section
    response = requests.post(url, json={'query': query, 'variables': variables}, headers=headers)
    data = response.json()
    return data

def create_order(client, mongo_url, url, email, password):
    st.write("Sure, I can help you with that. Please input the following details or upload an Excel file.")

    # Using columns to separate mandatory and optional fields
    col1, col2 = st.columns([1, 1.5])

    with col1:
        st.markdown("""
        **Mandatory Fields**:
        - 📦 Warehouse Name/Code
        - 👤 Customer Name/Code
        - 🔖 Product SKU
        - 🔢 Quantity
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        **Optional Fields**:
        - 📅 Order Date (Leave blank to use current date and time)
        - 📐 Form Factor (Each, Case, Carton, Pallet)
        - 🚚 Carrier (UPS, USPS, FedEx)
        - 🆔 Order ID (Leave blank to auto-generate)
        - 🛡️ Insurance Required
        - 🔍 Product Lot/Batch ID
        - 📦 Shipping Address
        - ✅ Validate Address
        """, unsafe_allow_html=True)


    # Expander for text input details
    with st.expander("Enter Order Details Here:"):
        order_details = st.text_area("Fill in the details for the mandatory fields and any optional fields you wish to include.")
        if order_details:
            # Check for missing mandatory fields
            missing_fields_response = check_mandatory_fields(order_details, client)
            if "All mandatory fields are present" in missing_fields_response:
                order = json_from_user_input(order_details, client)
                validate, validated_order = validate_fields(order, client, mongo_url)
                if validate == "Yes":
                    order_data = create_order_data(validated_order, client, mongo_url)
                    token = login(url, email, password, logout_all=True)
                    response = save_order(url, token, order_data)
                    print(response)
                    if 'data' in response and response['data']:
                        if any(success_message in response['data'].get('saveOrder', {}).get('message', '') for success_message in ("Order saved successfully", "Order successfully saved")):
                            st.success("Order created successfully")
                        else:
                            st.error("Order creation failed")
                    elif 'errors' in response:
                        st.error(f"{response['errors']}")
                    else:
                        st.error("An unknown error occurred")
                else:
                    st.error(f"{validate}")

            else:
                st.error(f"{missing_fields_response}")


    # Button for uploading Excel within an expander for better organization
    with st.expander("Or Upload an Excel File with Order Details:"):
        excel_file = st.file_uploader("", type=['xlsx'])
        if excel_file:
            st.success("Excel file uploaded successfully.")
            # Process Excel file here



def process_user_input(user_input, client, mongo_url, url, email, password):

    prompt = f"""
    You will be provided with the user's text delimited by triple quotes.
    If the user wants to create an order, write "Create order".

    If the user wants to create a product listing or shipment plan, \
    write "This feature is coming soon".

    If it contains anything other than creation of order, product or shipment, \
     return "I'm sorry, I can't help with that".

    \"\"\"{user_input}\"\"\"
    """
    response = get_completion(prompt, client)

    if response == "Create order":
        create_order(client, mongo_url, url, email, password)

    else:
        st.write(response)
        continue_response = st.text_input("If you want to continue with creating an order, type 'yes' otherwise 'no' to end this chat.")

        if continue_response.lower() == 'yes':
            create_order(client, mongo_url, url, email, password)
        elif continue_response.lower() == 'no':
            st.write("Thank you! If you need further assistance, just ask.")

# Main app logic
def main():

    client = OpenAI(
        # This is the default and can be omitted
        api_key=st.secrets["OPENAI_API_KEY"],
    )

    mongo_url = st.secrets["UAT"]
    email = st.secrets["email"]
    password = st.secrets["password"]
    url = st.secrets["url"]

    display_greeting()

    user_input = st.text_input("Your response:")

    if user_input:
        process_user_input(user_input, client, mongo_url, url, email, password)

if __name__ == "__main__":
    main()
