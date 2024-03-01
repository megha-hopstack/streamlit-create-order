# Streamlit Chat Assistant

This Streamlit application integrates OpenAI's GPT-4, MongoDB, and a GraphQL API to assist users in creating orders and managing other tasks within a platform.

## Features

- **Natural Language Processing**: Leverages OpenAI's GPT-4 model to understand and process user inputs.
- **Order Creation**: Allows users to create orders by providing details through a chat interface or uploading an Excel file.
- **Input Validation**: Validates user inputs against the MongoDB database for fields like warehouse names, customer codes, and product SKUs.
- **GraphQL API Integration**: Interacts with a GraphQL API for authentication and order saving.

## Prerequisites

- Python 3.8 or later
- Streamlit
- OpenAI
- MongoDB
- Requests
- Pandas
- dotenv

## Usage

- Enter the tenant name to start interacting with the chat assistant.
- Follow the prompts to create orders or perform other actions.

## Fields and Validation

### Mandatory Fields

- **Warehouse Name/Code**: The name or code of the warehouse where the order will be processed.
- **Customer Name/Code**: The name or code of the customer placing the order.
- **Product SKU**: The stock keeping unit (SKU) of the product being ordered.
- **Quantity**: The number of units of the product being ordered.

### Optional Fields

- **Order Date**: The date the order is placed. Defaults to the current date and time if not provided.
- **Form Factor**: The packaging form factor (e.g., each, case, carton, pallet).
- **Carrier**: The shipping carrier (e.g., UPS, USPS, FedEx).
- **Order ID**: A unique identifier for the order. Auto-generated if not provided.
- **Insurance Required**: Indicates whether insurance is required for the shipment.
- **Product Lot/Batch ID**: The lot or batch ID of the product.
- **Shipping Address**: The address where the order will be shipped.
- **Validate Address**: Indicates whether the shipping address should be validated.

### Validation Process

- **Tenant**: The tenant name is validated against the `tenants` collection in the MongoDB database to ensure it exists and is active.
- **Customer**: The customer name/code is validated against the `customers` collection in the MongoDB database to ensure it exists within the specified tenant.
- **Warehouse**: The warehouse name/code is validated against the `warehouses` collection in the MongoDB database to ensure it exists within the specified tenant.
- **SKU**: The product SKU is validated against the `productvariants` collection in the MongoDB database to ensure it exists and is associated with the specified customer and warehouse.
- **Order Date**: If provided, the order date is validated to ensure it is in a valid format and converted to epoch time in milliseconds.
- **Quantity**: The quantity is validated to ensure it is a positive number.
- **Form Factor**: If provided, the form factor is validated against a predefined list of valid form factors.
- **Carrier**: If provided, the carrier is validated against a predefined list of valid carriers.
- **Insurance Required**: If provided, it is validated to be either "yes" or "no".
- **Validate Address**: If provided, it is validated to be either "yes" or "no".
