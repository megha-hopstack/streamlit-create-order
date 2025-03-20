import streamlit as st
import os
from openai import OpenAI
from pymongo import MongoClient
import json
from bson import ObjectId
import requests
import time
import pandas as pd

def get_completion(prompt, client_instance, model="gpt-4o"):
    messages = [{"role": "user", "content": prompt}]
    response = client_instance.chat.completions.create(
    model=model,
    messages=messages,
    max_tokens=500,
    temperature=0,
    )
    return response.choices[0].message.content

def get_completion_json(prompt, client_instance, model="gpt-4o"):
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

def check_tenant_name(tenant_name, database):
    result = database.tenants.find_one({"name": tenant_name, "subdomain": "uat"}, {"_id": 1})
    if result:
        return str(result['_id'])
    return "Tenant name not valid"

def display_greeting(database):
    st.title("Welcome to Our Chat Assistant")

    with st.expander("Enter Tenant Name:"):
        tenant_name = st.text_input("Please enter the tenant name:", key="tenant_name_input")
        if tenant_name:
            tenant_id = check_tenant_name(tenant_name, database)
            if tenant_id != "Tenant name not valid":
                st.session_state['tenant_id'] = tenant_id
                st.session_state['tenant_name'] = tenant_name
                st.write(f"What would you like to do today, {tenant_name}? Here are some things I can help you with:")

                # Create three columns for the options
                col1, col2, col3 = st.columns(3)

                # Display each option in its own box within a column
                with col1:
                    st.container()
                    st.write("📦 Create Order")

                with col2:
                    st.container()
                    st.write("🚚 Create Consignment")

                with col3:
                    st.container()
                    st.write("📝 Create Product Listing")

                st.write("Please type your request below.")
            else:
                st.error("Tenant name not valid. Please try again.")

    return st.session_state.get('tenant_id'), st.session_state.get('tenant_name')


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

    Check if all the specified mandatory fields are present in the user's input. \
    The name of the fields need not exactly match the user's input. Use your discretion to understand if the given fields and user's inputs match.\
    If any of the specified mandatory fields are missing, return "Mandatory fields missing: " followed by the list of missing fields. \
    If all specified mandatory fields are present, respond with "All mandatory fields are present".
    Do not respond with anything other than either the missing fields list or "All mandatory fields are present".
    """

    response = get_completion(prompt, client)
    return response

#Function to return json from user input
def json_from_user_input_order(user_input, client):
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

#Function to return json from user input
def json_from_user_input_consignment(user_input, client):
    mandatory_fields = [
        "Warehouse Name/Code",
        "Customer Name/Code",
        "Product SKU",
        "Quantity",
        "Standard/Dropship"
    ]
    optional_fields = [
        "Consignment Date",
        "Order ID",
        "Consignment Number",
        "Supplier/Vendor",
        "Form Factor",
        "Carrier",
        "Tracking Number",
        "Dropship Type",
        "Dropship Data",
    ]

    prompt = f"""
    The user's input is: "{user_input}"
    The mandatory fields are: {mandatory_fields}.
    The optional fields are: {optional_fields}.

    Return a JSON object where keys are all the fields in {mandatory_fields} and {optional_fields}. Extract the respective values from the user input.
    For example: if user writes warehouse 554, then the dictionary should contain key as "Warehouse Name/Code" and value as "554".
    The name of the fields need not exactly match the user's input. Use your discretion to understand which part of the user's input refers to which key.
    For any optional field leave the value blank if it is not input by the user, but do not leave the keys blank.
    """

    response = get_completion_json(prompt, client)
    response_dict = json.loads(response)  # Convert the JSON string to a Python dictionary
    return response_dict


def validate_warehouse(warehouse_code, database, tenant_id):
    result = database.warehouses.find_one(
        {"tenant": tenant_id, "$or": [{"name": warehouse_code}, {"code": warehouse_code}]},
        {"_id": 1}
    )
    if result:
        return str(result['_id'])
    else:
        return "Warehouse name/code not valid"

def validate_customer(customer_code, database, tenant_id):
    result = database.customers.find_one(
        {"tenant": tenant_id, "$or": [{"name": customer_code}, {"code": customer_code}]},
        {"_id": 1}
    )
    if result:
        return str(result['_id'])
    else:
        return "Customer name/code not valid"

def validate_customer_warehouse_access(customer_id, warehouse_id, database):
    # Convert warehouse_id to ObjectId
    warehouse_id = ObjectId(warehouse_id)

    # Retrieve the customer document
    customer = database.customers.find_one({"_id": ObjectId(customer_id)}, {"warehouses": 1})

    # Check if the customer has access to all warehouses or the specific warehouse
    if customer.get("warehouses") is None or str(warehouse_id) in customer.get("warehouses", []):
        return True
    else:
        return "Warehouse not valid for this customer"

def validate_order_date(order_date, client):
    prompt = f"""Is '{order_date}' a valid date? If not, respond with "Date not valid".
    If yes, convert it to epoch time in milliseconds and return that. Assume the timezone is UTC.
    Do not respond with anything other than either the epoch time or "Date not valid".
    """
    response = get_completion(prompt, client)

    try:
        epoch_time = int(response)
        current_time = int(time.time() * 1000)

        if epoch_time > current_time:
            return "Date not valid"

        return response
    except ValueError:
        return "Date not valid"

def validate_quantity(quantity, client):
    prompt = f"""Is '{quantity}' a valid positive number or a word representing a positive number? If not, respond with "Quantity not valid".
            If it is an integer, simply return that. If it is a word representing a positive number, return the integer it respresents. Don't respond with anything else."""
    response = get_completion(prompt, client)
    return response

def validate_product_sku(customer, sku, database, tenant_id):
    # Find the product variant that matches the SKU, customer, and tenant
    result = database.productvariants.find_one(
        {"tenant": tenant_id, "customer": customer, "sku": sku},
        {"_id": 1}
    )
    if result:
        return str(result['_id'])
    else:
        return "SKU not valid"

def validate_form_factor_order(form_factor):
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

def validate_form_factor_consignment(customer, sku, database, tenant_id, form_factor):
    # Find all product variants that match the given customer, SKU, and tenant
    results = database.productvariants.find(
        {"tenant": tenant_id, "customer": customer, "sku": sku},
        {"uomConfiguration": 1, "baseUom": 1}
    )

    # Normalize the form factor input (case-insensitive comparison)
    form_factor_lower = form_factor.lower()

    # Iterate over each matching result
    for result in results:
        # Check the baseUom
        base_uom = result.get('baseUom', '').lower()

        # Check if form_factor matches baseUom
        if form_factor_lower == base_uom:
            return form_factor

        # Check the uomConfiguration if it exists
        uom_configurations = result.get('uomConfiguration', [])
        for config in uom_configurations:
            if form_factor_lower == config.get('baseUom', '').lower() or form_factor_lower == config.get('targetUom', '').lower():
                return form_factor

    # If no match is found in any result, return "Form factor not valid"
    return "Form factor not valid"


def validate_and_format_dropship_data(dropship_type, dropship_data):
    missing_fields = []

    # Prepare a dictionary to hold the formatted data
    formatted_data = {}

    # FBA Validation
    if dropship_type.lower() == "fba":
        is_case = dropship_data.get("Is Case", None)
        per_case_quantity = dropship_data.get("Per Case Quantity", None)
        number_of_cases = dropship_data.get("Number of Cases", None)

        # Add to formatted data
        formatted_data["Is Case"] = is_case
        formatted_data["Per Case Quantity"] = per_case_quantity
        formatted_data["Number of Cases"] = number_of_cases

        # Check for required FBA fields
        if not is_case:
            missing_fields.append("Is Case")
        if is_case and is_case.lower() == "yes":  # If it's a case shipment
            if not per_case_quantity:
                missing_fields.append("Per Case Quantity")
            if not number_of_cases:
                missing_fields.append("Number of Cases")

    # Regular Dropship Validation
    elif dropship_type.lower() == "regular":
        label_source = dropship_data.get("Label Source", None)

        # Add to formatted data
        formatted_data["Label Source"] = label_source

        # Check for Label Source
        if not label_source:
            missing_fields.append("Label Source")
        else:
            if label_source.lower() == "public url":
                label_url = dropship_data.get("Label URL", None)
                formatted_data["Label URL"] = label_url

                if not label_url or not validators.url(label_url):  # Validate URL
                    missing_fields.append("Valid Label URL")
            elif label_source.lower() == "system generated":
                shipping_address = dropship_data.get("Shipping Address", {})
                formatted_data["Shipping Address"] = shipping_address

                # Even though the shipping address is optional, we will add it to the formatted data
                # if the fields are provided (they can be left blank)
                required_address_fields = ["name", "email", "phone", "line1", "zip", "country", "city", "state"]
                for field in required_address_fields:
                    if field in shipping_address:
                        formatted_data["Shipping Address"][field] = shipping_address.get(field, "")

    # If there are missing fields, return an error message with those details
    if missing_fields:
        return {"error": f"Missing or invalid fields: {', '.join(missing_fields)}"}

    # Return the formatted data for creating the final JSON
    return formatted_data

def validate_order_fields(order, client, database, tenant_id):
    print(order)
    validated_order = order.copy()

    # Validate customer
    customer_id = validate_customer(order["Customer Name/Code"], database, tenant_id)
    if customer_id == "Customer name/code not valid":
        return customer_id, None

    # Validate warehouse
    warehouse_id = validate_warehouse(order["Warehouse Name/Code"], database, tenant_id)
    if warehouse_id == "Warehouse name/code not valid":
        return warehouse_id, None

    access_check = validate_customer_warehouse_access(customer_id, warehouse_id, database)
    if access_check != True:
        return access_check, None

    #Validate order date
    order_date = order.get("Order Date", "")
    if order_date:
        order_date_epoch = validate_order_date(order_date, client)
        if order_date_epoch == "Date not valid":
            return order_date_epoch, None
        validated_order["Order Date"] = int(order_date_epoch)
    else:
        validated_order["Order Date"] = int(time.time() * 1000)  # Current time in milliseconds

    # Validate quantity
    quantity = validate_quantity(order["Quantity"], client)
    if quantity == "Quantity not valid":
        return quantity, None
    validated_order["Quantity"] = int(quantity)

    # Validate product SKU
    sku_id = validate_product_sku(customer_id, order["Product SKU"], database, tenant_id)
    if sku_id == "SKU not valid":
        return sku_id, None

    # Update the validated_order with the matched warehouse and customer IDs
    validated_order["Warehouse ID"] = warehouse_id
    validated_order["Customer ID"] = customer_id
    validated_order["Product SKU ID"] = sku_id

    # Validate form factor
    form_factor = validate_form_factor_order(order.get("Form Factor"))
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


def create_order_data(validated_order, client, database):

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
        "source": "Hopstack"
    }

    return order_data

def validate_consignment_fields(consignment, client, database, tenant_id):
    print(consignment)
    validated_consignment = consignment.copy()
    
    # Validate customer
    customer_id = validate_customer(consignment["Customer Name/Code"], database, tenant_id)
    if customer_id == "Customer name/code not valid":
        return customer_id, None
    
    # Validate warehouse
    warehouse_id = validate_warehouse(consignment["Warehouse Name/Code"], database, tenant_id)
    if warehouse_id == "Warehouse name/code not valid":
        return warehouse_id, None
    
    access_check = validate_customer_warehouse_access(customer_id, warehouse_id, database)
    if access_check != True:
        return access_check, None
    
    # Validate consignment date
    consignment_date = consignment.get("Consignment Date", "")
    if consignment_date:
        consignment_date_epoch = validate_order_date(consignment_date, client)
        if consignment_date_epoch == "Date not valid":
            return consignment_date_epoch, None
        validated_consignment["Consignment Date"] = consignment_date_epoch
    else:
        validated_consignment["Consignment Date"] = int(time.time() * 1000)  # Current time in milliseconds
    
    # Validate quantity
    quantity = validate_quantity(consignment["Quantity"], client)
    if quantity == "Quantity not valid":
        return quantity, None
    validated_consignment["Quantity"] = quantity
    
    # Validate product SKU
    sku_id = validate_product_sku(customer_id, consignment["Product SKU"], database, tenant_id)
    if sku_id == "SKU not valid":
        return sku_id, None
    
    # Update the validated_consignment with the matched warehouse and customer IDs
    validated_consignment["Warehouse ID"] = warehouse_id
    validated_consignment["Customer ID"] = customer_id
    validated_consignment["Product SKU ID"] = sku_id
    
    # Validate form factor
    if not consignment["Form Factor"] == '':
        form_factor = validate_form_factor_consignment(customer_id, consignment["Product SKU"], database, tenant_id, consignment["Form Factor"])
        if form_factor == "Form factor not valid":
            return form_factor, None
        validated_consignment["Form Factor"] = form_factor
    
    
    # Validate dropship-specific fields (if applicable)
    if consignment.get("Standard/Dropship", "").lower() == "dropship":
        # Validate dropship type and dropship data
        dropship_type = consignment.get("Dropship Type", "")
        dropship_data = {
            "Is Case": consignment.get("Is Case"),
            "Per Case Quantity": consignment.get("Per Case Quantity"),
            "Number of Cases": consignment.get("Number of Cases"),
            "Label Source": consignment.get("Label Source"),
            "Label URL": consignment.get("Label URL"),
            "Shipping Address": consignment.get("Shipping Address")
        }
    
        validation_result = validate_and_format_dropship_data(dropship_type, dropship_data)
    
        if "error" in validation_result:
            return validation_result["error"], None
    
        # If valid, add the dropship data to the validated consignment
        validated_consignment["Dropship Type"] = dropship_type
        validated_consignment["Dropship Data"] = validation_result
    
    return "Yes", validated_consignment

def create_consignment_data(validated_consignment, client, database):
    # Initialize the common consignment data
    consignment_data = {
        "warehouse": validated_consignment["Warehouse ID"],
        "customer": validated_consignment["Customer ID"],
        "warehouseToBeSelected": True,
        "customerToBeSelected": True,
        "items": []
    }

    # Query the productvariants collection
    sku_id = validated_consignment["Product SKU ID"]

    product_variant = database.productvariants.find_one(
        {"_id": ObjectId(sku_id)},
        {"_id": 1, "sku": 1, "asin": 1, "sellerSku": 1, "name": 1, "baseUom": 1}
    ) or {}

    form_factor = validated_consignment.get("Form Factor")
    if not form_factor:
        form_factor = product_variant.get("baseUom")

    # Add item information
    item_data = {
        "productId": sku_id,
        "fulfillmentType": "FBA",
        "asin": product_variant.get("asin", None),
        "sku": product_variant.get("sku"),
        "sellerSku": product_variant.get("sellerSku", None),
        "productName": product_variant.get("name", None),
        "formFactor": form_factor,
        "formFactors": [
            {
                "name": form_factor,
                "quantity": validated_consignment["Quantity"]
            }
        ]
    }

    # Add to the items array
    consignment_data["items"].append(item_data)

    # Add consignment-specific fields
    consignment_data["orderId"] = validated_consignment.get("Order ID")
    consignment_data["consignmentNumber"] = validated_consignment.get("Consignment Number")
    consignment_data["supplier"] = validated_consignment.get("Supplier/Vendor")
    consignment_data["consignmentDate"] = validated_consignment.get("Consignment Date")
    consignment_data["carrier"] = validated_consignment.get("Carrier")
    consignment_data["status"] = validated_consignment.get("Status", "FINAL")

    # Add tracking numbers if present
    tracking_numbers = validated_consignment.get("Tracking Number", [])
    if tracking_numbers:
        consignment_data["trackingNumber"] = tracking_numbers

    # Handle dropship-specific fields
    if validated_consignment.get("Standard/Dropship", "").lower() == "dropship":
        consignment_data["dropship"] = True
        consignment_data["dropshipType"] = validated_consignment.get("Dropship Type", "DEFAULT")

        # Handle FBA case
        if consignment_data["dropshipType"].lower() == "fba":
            item_data["quantityInCase"] = validated_consignment.get("Per Case Quantity", 1)
            item_data["numberOfCases"] = validated_consignment.get("Number of Cases", 1)
            consignment_data["isCasePack"] = True

        # Handle dropship data (label source, etc.)
        dropship_data = validated_consignment.get("Dropship Data", {})
        consignment_data["dropshipData"] = dropship_data

    # Handle shipping address (optional)
    shipping_address = validated_consignment.get("Shipping Address", {})
    if shipping_address:
        consignment_data["shippingAddress"] = {
            "name": shipping_address.get("name"),
            "email": shipping_address.get("email"),
            "phone": shipping_address.get("phone"),
            "line1": shipping_address.get("line1"),
            "line2": shipping_address.get("line2"),
            "zip": shipping_address.get("zip"),
            "country": shipping_address.get("country"),
            "city": shipping_address.get("city"),
            "state": shipping_address.get("state")
        }

    return consignment_data

def login(url, username, password, tenant_id, tenant_name, logout_all=True):
    headers = {'Content-Type': 'application/json',
              'tenant': f'{{"id":"{tenant_id}","name":"{tenant_name}","subdomain":"uat","code":"uat", "active": true}}'
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

def save_order(url, token, order_data, tenant_id, tenant_name):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}',
        'tenant': f'{{"id":"{tenant_id}","name":"{tenant_name}","subdomain":"uat","code":"uat", "active": true}}'
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
    $source: String
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
        source: $source
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

def save_consignment(url, token, consignment_data, tenant_id, tenant_name):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}',
        'tenant': f'{{"id":"{tenant_id}","name":"{tenant_name}","subdomain":"uat","code":"uat", "active": true}}'
    }

    # GraphQL mutation for saving a consignment
    query = """
    mutation saveConsignment(
      $trackingNumber: [String]
      $items: [ConsignmentInputItem!]
      $customer: ID
      $warehouse: ID
      $consignmentNumber: String
      $orderId: String
      $id: ID
      $supplier: String
      $carrier: String
      $consignmentDate: Date
      $notes: String
      $isReturnOrder: Boolean
      $linkedOrders: [Random]
      $status: String
      $dropship: Boolean
      $dropshipType: String
      $typeOfShipment: String
      $shippingAddress: ShippingAddressInput
      $dropshipData: Random
      $workingList: [Random]
      $isCasePack: Boolean
      $sellerId: String
    ) {
      saveConsignment(
        consignmentInput: {
          trackingNumber: $trackingNumber
          items: $items
          customer: $customer
          warehouse: $warehouse
          consignmentNumber: $consignmentNumber
          orderId: $orderId
          id: $id
          supplier: $supplier
          carrier: $carrier
          consignmentDate: $consignmentDate
          notes: $notes
          isReturnOrder: $isReturnOrder
          linkedOrders: $linkedOrders
          status: $status
          dropship: $dropship
          dropshipType: $dropshipType
          shippingAddress: $shippingAddress
          typeOfShipment: $typeOfShipment
          dropshipData: $dropshipData
          workingList: $workingList
          isCasePack: $isCasePack
          sellerId: $sellerId
        }
      ) {
        message
      }
    }
    """

    # Sending the consignment data as variables for the mutation
    variables = consignment_data  # Consignment data should be a properly structured dictionary
    response = requests.post(url, json={'query': query, 'variables': variables}, headers=headers)
    data = response.json()

    # Return the message or any error
    return data

def create_order(client, database, url, email, password, tenant_id, tenant_name):
    st.write("Sure, I can help you with that. Please input the following details or upload a CSV file.")

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
        order_input = st.text_area("Enter order details here:")
        if st.button("Add Order"):
            if order_input.strip():
                missing_fields_response = check_mandatory_fields(order_input, client)
                if "All mandatory fields are present" in missing_fields_response:
                    order_data = json_from_user_input_order(order_input, client)
                    validate, validated_order = validate_order_fields(order_data, client, database, tenant_id)
                    if validate == "Yes":
                        if 'orders' not in st.session_state:
                            st.session_state.orders = []
                        st.session_state.orders.append(validated_order)
                        st.success("Order added. Add another or submit all orders.")
                    else:
                        st.error(f"Validation failed: {validate}")
                else:
                    st.error(f"Missing mandatory fields: {missing_fields_response}")

    # Display list of orders
    st.markdown("### Orders to be Submitted")
    if 'orders' in st.session_state and st.session_state.orders:
        with st.expander(f"View {len(st.session_state.orders)} Orders to be Submitted"):
            for i, order in enumerate(st.session_state.orders, 1):
                st.write(f"**Order {i}:**")
                st.json(order)

        # Final Submit Button
        if st.button("Submit All Orders"):
            token = login(url, email, password, tenant_id, tenant_name)
            progress_bar = st.progress(0)
            total_orders = len(st.session_state.orders)
            for i, order in enumerate(st.session_state.orders, 1):
                order_payload = create_order_data(order, client, database)
                response = save_order(url, token, order_payload, tenant_id, tenant_name)
                if 'data' in response and response['data']:
                    if any(success_message in response['data'].get('saveOrder', {}).get('message', '') for success_message in ("Order saved successfully", "Order successfully saved")):
                        st.toast(f"Order {i} created successfully", icon="✅")
                    else:
                        st.toast(f"Order {i} creation failed: {response['data'].get('saveOrder', {}).get('message', 'Unknown error')}", icon="❌")
                elif 'errors' in response:
                    st.toast(f"Order {i} errors: {response['errors']}", icon="❌")
                else:
                    st.toast(f"An unknown error occurred with Order {i}", icon="❌")
                progress_bar.progress(i / total_orders)
            st.session_state.orders = []  # Clear orders after submission
    else:
        st.write("No orders added yet.")

    # Button for uploading CSV within an expander for better organization
    with st.expander("Or Upload a CSV File with Order Details:"):
        csv_file = st.file_uploader("", type=['csv'])
        if csv_file:
            try:
                df = pd.read_csv(csv_file)

                for index, row in df.iterrows():
                    # Convert row to dictionary and prepare order details string
                    row_dict = row.to_dict()
                    order_details = ", ".join([f"{k}: {v}" for k, v in row_dict.items() if pd.notna(v)])

                    # Check for missing mandatory fields
                    missing_fields_response = check_mandatory_fields(order_details, client)
                    if "All mandatory fields are present" in missing_fields_response:
                        order = json_from_user_input_order(order_details, client)
                        validate, validated_order = validate_order_fields(order, client, database, tenant_id)
                        if validate == "Yes":
                            if 'orders' not in st.session_state:
                                st.session_state.orders = []
                            st.session_state.orders.append(validated_order)
                            st.success(f"Order from row {index+1} added.")
                        else:
                            st.error(f"Validation failed for row {index+1}: {validate}")
                    else:
                        st.error(f"Missing mandatory fields for row {index+1}: {missing_fields_response}")
            except Exception as e:
                st.error("Cannot read CSV: " + str(e))

def create_consignment(client, database, url, email, password, tenant_id, tenant_name):
    st.write("Sure, I can help you with that. Please input the following consignment details or upload a CSV file.")

    # Using columns to separate mandatory and optional fields
    col1, col2 = st.columns([1, 1.5])

    with col1:
        st.markdown("""
        **Mandatory Fields**:
        - 📦 Warehouse Name/Code
        - 👤 Customer Name/Code
        - 🔖 Product SKU
        - 🔢 Quantity
        - 🏷️ Standard/Dropship
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        **Optional Fields**:
        - 📅 Consignment Date
        - 🆔 Order ID
        - 🛠️ Consignment Number
        - 🛒 Supplier/Vendor
        - 📐 Form Factor
        - 🚚 Carrier
        - 🏷️ Tracking Number
        - 🏷️ **Dropship Type**: Specify whether the dropship is **FBA** or **Regular**.
        - 🏷️ **Dropship Data**:
            - If **FBA**, provide details for:
                - **Is Case**: Whether the consignment is shipped as a case.
                - **Per Case Quantity**: The number of items per case.
                - **Number of Cases**: The total number of cases.
            - If **Regular**, provide:
                - **Label Source**: Specify how the label will be provided (Public URL or System Generated).
                - **Label Data**: Depending on the label source, provide the URL or shipping address.
        """, unsafe_allow_html=True)

    # Expander for text input details
    with st.expander("Enter Consignment Details Here:"):
        consignment_input = st.text_area("Enter consignment details here:")
        if st.button("Add Consignment"):
            if consignment_input.strip():
                missing_fields_response = check_mandatory_fields(consignment_input, client)
                if "All mandatory fields are present" in missing_fields_response:
                    consignment_data = json_from_user_input_consignment(consignment_input, client)
                    validate, validated_consignment = validate_consignment_fields(consignment_data, client, database, tenant_id)
                    if validate == "Yes":
                        if 'consignments' not in st.session_state:
                            st.session_state.consignments = []
                        st.session_state.consignments.append(validated_consignment)
                        st.success("Consignment added. Add another or submit all consignments.")
                    else:
                        st.error(f"Validation failed: {validate}")
                else:
                    st.error(f"Missing mandatory fields: {missing_fields_response}")

    # Display list of consignments
    st.markdown("### Consignments to be Submitted")
    if 'consignments' in st.session_state and st.session_state.consignments:
        with st.expander(f"View {len(st.session_state.consignments)} Consignments to be Submitted"):
            for i, consignment in enumerate(st.session_state.consignments, 1):
                st.write(f"**Consignment {i}:**")
                st.json(consignment)

        # Final Submit Button
        if st.button("Submit All Consignments"):
            token = login(url, email, password, tenant_id, tenant_name)
            progress_bar = st.progress(0)
            total_consignments = len(st.session_state.consignments)
            for i, consignment in enumerate(st.session_state.consignments, 1):
                consignment_payload = create_consignment_data(consignment, client, database)
                response = save_consignment(url, token, consignment_payload, tenant_id, tenant_name)
                if 'data' in response and response['data']:
                    if any(success_message in response['data'].get('saveConsignment', {}).get('message', '') for success_message in ("Consignment added successfully", "Consignment successfully added")):
                        st.toast(f"Consignment {i} created successfully", icon="✅")
                    else:
                        st.toast(f"Consignment {i} creation failed: {response['data'].get('saveConsignment', {}).get('message', 'Unknown error')}", icon="❌")
                elif 'errors' in response:
                    st.toast(f"Consignment {i} errors: {response['errors']}", icon="❌")
                else:
                    st.toast(f"An unknown error occurred with Consignment {i}", icon="❌")
                progress_bar.progress(i / total_consignments)
            st.session_state.consignments = []  # Clear consignments after submission
    else:
        st.write("No consignments added yet.")

    # Button for uploading CSV within an expander for better organization
    with st.expander("Or Upload a CSV File with Consignment Details:"):
        csv_file = st.file_uploader("", type=['csv'])
        if csv_file:
            try:
                df = pd.read_csv(csv_file)

                for index, row in df.iterrows():
                    # Convert row to dictionary and prepare consignment details string
                    row_dict = row.to_dict()
                    consignment_details = ", ".join([f"{k}: {v}" for k, v in row_dict.items() if pd.notna(v)])

                    # Check for missing mandatory fields
                    missing_fields_response = check_mandatory_fields(consignment_details, client)
                    if "All mandatory fields are present" in missing_fields_response:
                        consignment = json_from_user_input_consignment(consignment_details, client)
                        validate, validated_consignment = validate_consignment_fields(consignment, client, database, tenant_id)
                        if validate == "Yes":
                            if 'consignments' not in st.session_state:
                                st.session_state.consignments = []
                            st.session_state.consignments.append(validated_consignment)
                            st.success(f"Consignment from row {index+1} added.")
                        else:
                            st.error(f"Validation failed for row {index+1}: {validate}")
                    else:
                        st.error(f"Missing mandatory fields for row {index+1}: {missing_fields_response}")
            except Exception as e:
                st.error("Cannot read CSV: " + str(e))


def process_user_input(user_input, client, database, url, email, password, tenant_id, tenant_name):

    prompt = f"""
    You will be provided with the user's text delimited by triple quotes.
    If the user wants to create an order, write "Create order".

    If the user wants to create a consignment, write "Create consignment".

    If the user wants to create a product listing or shipment plan, \
    write "This feature is coming soon".

    If it contains anything other than creation of order, product or shipment, \
     return "I'm sorry, I can't help with that".

    \"\"\"{user_input}\"\"\"
    """
    response = get_completion(prompt, client)

    if response == "Create order":
        create_order(client, database, url, email, password, tenant_id, tenant_name)

    elif response == "Create consignment":
        create_consignment(client, database, url, email, password, tenant_id, tenant_name)

    else:
        st.write(response)
        continue_response = st.text_input("If you want to continue with creating an order or consignment, type 'yes' otherwise 'no' to end this chat.")

        if continue_response.lower() == 'yes':
            create_order(client, database, url, email, password, tenant_id, tenant_name)
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

    database = database_connection(mongo_url)
    tenant_id, tenant_name = display_greeting(database)

    if tenant_id and tenant_name:
        user_input = st.text_input("Your response:")
        if user_input:
            process_user_input(user_input, client, database, url, email, password, tenant_id, tenant_name)


if __name__ == "__main__":
    main()
