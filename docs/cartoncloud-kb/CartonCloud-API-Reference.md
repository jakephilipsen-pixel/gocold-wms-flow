# CartonCloud API Reference

_Offline copy of https://api-docs.cartoncloud.com/ — the complete CartonCloud REST API reference (auth, endpoints, request/response schemas, code samples). Captured for API-feasibility planning._

## Contents

- [Introduction](#introduction)
- [Postman Collection](#postman-collection)
- [Environments](#environments)
- [Authentication](#authentication)
  - [Client Credentials](#client-credentials)
  - [Access Token](#access-token)
  - [Software Vendors](#software-vendors)
- [Account Info](#account-info)
  - [User](#user)
- [General](#general)
  - [Version](#version)
  - [Tenant](#tenant)
  - [Pagination](#pagination)
  - [Optional Fields](#optional-fields)
- [Customers](#customers)
  - [Create Customer](#create-customer)
  - [List Customers](#list-customers)
  - [Get Customer](#get-customer)
- [Inbound Orders (Purchase Orders)](#inbound-orders-purchase-orders)
  - [Create Inbound Order](#create-inbound-order)
  - [Get Inbound Order](#get-inbound-order)
  - [Update Inbound Order](#update-inbound-order)
  - [Delete Inbound Order](#delete-inbound-order)
  - [Search Inbound Orders](#search-inbound-orders)
- [Outbound Orders (Sale Orders)](#outbound-orders-sale-orders)
  - [Create Outbound Order](#create-outbound-order)
  - [Get Outbound Order](#get-outbound-order)
  - [Update Outbound Order (sale order)](#update-outbound-order-sale-order)
  - [Delete Outbound Order](#delete-outbound-order)
  - [Search Outbound Orders](#search-outbound-orders)
  - [Create Outbound Document](#create-outbound-document)
  - [Get Outbound Document](#get-outbound-document)
  - [Download Outbound Document](#download-outbound-document)
  - [List Outbound Documents](#list-outbound-documents)
- [Warehouse Products](#warehouse-products)
  - [Create Warehouse Product](#create-warehouse-product)
  - [Get Product](#get-product)
  - [Update Product (PUT)](#update-product-put)
  - [Partial Product Update (PATCH)](#partial-product-update-patch)
  - [Search Warehouse Products](#search-warehouse-products)
- [Consignments](#consignments)
  - [Create Consignment](#create-consignment)
  - [Get Consignment](#get-consignment)
  - [Update Consignment](#update-consignment)
  - [Search Consignment](#search-consignment)
  - [Get Quote](#get-quote)
- [Transport Products](#transport-products)
  - [Create Transport Product](#create-transport-product)
  - [List Transport Products](#list-transport-products)
  - [Get Transport Product](#get-transport-product)
- [Documents](#documents)
  - [Create Document](#create-document)
- [Reports](#reports)
  - [Create report run](#create-report-run)
  - [Stock on hand report](#stock-on-hand-report)
  - [Bulk charges report](#bulk-charges-report)
  - [Get Report Run results](#get-report-run-results)
- [Standard Elements](#standard-elements)
  - [References](#references)
  - [Customer](#customer)
  - [Warehouse](#warehouse)
  - [Address](#address)
  - [State](#state)
  - [Country](#country)
  - [DeliveryMethod](#deliverymethod)
  - [Product](#product)
  - [UnitOfMeasure](#unitofmeasure)
  - [Money](#money)
  - [Delivery Run](#delivery-run)
  - [Run Sheet](#run-sheet)
  - [Manifest](#manifest)
  - [User](#user)
  - [Search Condition Types](#search-condition-types)
  - [Search Condition Json Field](#search-condition-json-field)
  - [Search Condition Value Field (deprecated)](#search-condition-value-field-deprecated)
  - [Timestamp](#timestamp)
  - [Error Reference](#error-reference)
  - [Custom Fields](#custom-fields)
- [Webhooks](#webhooks)
  - [Configuring Webhooks](#configuring-webhooks)
- [Responses](#responses)
  - [Success Status Codes](#success-status-codes)
  - [Error Status Codes](#error-status-codes)
  - [Error Response Data](#error-response-data)

---

## Introduction <a id="introduction"></a>

This is the official CartonCloud API documentation.

For general application documentation please refer to our [Knowledge Base](https://help.cartoncloud.com).

For information on Custom Fields, please refer to [Custom Fields in the API](https://help.cartoncloud.com/help/s/article/Custom-Fields-in-the-API)

`Accept-Version: 1`

*Last Updated: 2026-05-06 01:29*

## Postman Collection <a id="postman-collection"></a>

A publicly available Postman Collection is available here: [CartonCloud Public API Postman Collection](https://api.postman.com/collections/REDACTED?access_key=REDACTED)

This collection will be updated in-line with documentation changes.

For help using the Postman Collection, see the [Postman Setup for API Access](https://help.cartoncloud.com/kb2/web-app-page-specific-support/administrator-pages/contacts/api-clients#APIClients-PostmanSetupforAPIAccess) section of our [API Clients](https://help.cartoncloud.com/help/s/article/API-Clients) Knowledge Base Article

## Environments <a id="environments"></a>

CartonCloud API is available in different regional environments. Use the appropriate base URL for your region:

| Region | Base URL |
| --- | --- |
| Global (Default) | `https://api.cartoncloud.com` |
| North America | `https://api.na.cartoncloud.com` |

All API endpoints documented here use the Global base URL in examples. Replace `api.cartoncloud.com` with your region-specific subdomain as needed.

## Authentication <a id="authentication"></a>

CartonCloud authentication follows the [OAuth2](https://tools.ietf.org/html/rfc6749) specifications.

Tenants and customers integrating with the API are required to use the client credentials grant type to obtain an Access Token.

For information on generating API Keys, refer to our Knowledge Base Article: [API Clients](https://help.cartoncloud.com/help/s/article/API-Clients)

### Client Credentials <a id="client-credentials"></a>

An access token can be obtained using the client credentials

#### HTTP Request <a id="http-request"></a>

> Example Request

```bash
curl -u {clientId}:{clientSecret} \ 
   "https://api.cartoncloud.com/uaa/oauth/token" \
   -X POST \
   -H "Accept-Version: 1" \
   -H "Content-Type: application/x-www-form-urlencoded" \
   -d grant_type="client_credentials"
```

`POST https://api.cartoncloud.com/uaa/oauth/token`

#### Authentication <a id="authentication-2"></a>

The following client credentials can be obtained from a user with administrator access.
The clientId and clientSecret should be set in the [HTTP Basic Auth Header](https://tools.ietf.org/html/rfc7617)

| Credential | Description |
| --- | --- |
| clientId | The username for requests to the token end point |
| clientSecret | The password for requests to the token end point |

#### Request Parameters <a id="request-parameters"></a>

| Parameter | Description |
| --- | --- |
| grant_type | Must be `client_credentials` |

#### Response Properties <a id="response-properties"></a>

> Example Response JSON

```json
{
  "access_token": "{accessToken}",
  "token_type": "bearer",
  "expires_in": 3600
}
```

| Property | Description |
| --- | --- |
| access_token | Access token to be used to authenticate subsequent API requests |
| token_type | Will always be `bearer` |
| expires_in | The number of seconds after which the access token will expiry and will no longer be valid |

### Access Token <a id="access-token"></a>

> Example Request

```bash
# Send the access token with every request
curl "https://api_endpoint" \
  -H "Accept-Version: 1" \
  -H "Authorization: Bearer {accessToken}"
```

With every API request a valid access token must be supplied in the request header as a [Bearer Tokens](https://tools.ietf.org/html/rfc6750)

`Authorization: Bearer {accessToken}`

### Software Vendors <a id="software-vendors"></a>

Software vendors interested in providing out of the box integration into CartonCloud are required to use [OAuth2](https://tools.ietf.org/html/rfc6749) authorization code flow to connect.

## Account Info <a id="account-info"></a>

### User <a id="user"></a>

Returns information about the currently authenticated user.

#### Request <a id="request"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/uaa/userinfo" \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}"
```

`GET https://api.cartoncloud.com/uaa/userinfo`

#### Response <a id="response"></a>

> Example Response JSON

```json
{
  "id": "318782ea-75b1-11e8-adc0-fa7ae01b1234",
  "name": "John Smith",
  "email": "john.smith@cartoncloud.com",
  "tenants": [
    {
      "id": "318782ea-75b1-11e8-adc0-fa7ae01babab",
      "name": "Demo Tenant"
    }
  ]
}
```

On success will return status code `200 OK` with the user info in the response body.

| JSON Property | Description |
| --- | --- |
| id |  |
| name |  |
| email |  |
| tenants | id |
| tenants | name |

## General <a id="general"></a>

General features and requirements for API end points

### Version <a id="version"></a>

All API end points will require an Accept-Version in the request header.
Failure to provide the header will return a status code of `400`, however, an invalid version can return a `404` or `400`.

`Accept-Version: 1`

In general all changes to this API will be made in a non-breaking manner (fields added, but not removed).
However, if breaking changes are required the version number will be incremented.
The old version will be maintained for up to 12 months before being removed, or if no use is detected over 30 continuous days.

Fields or functionality not documented here may be removed or modified at anytime without version change or notice.

### Tenant <a id="tenant"></a>

All API end points, except for authentication, will be within the context of a tenant identified by a unique identifier (UUID)

#### Request <a id="request"></a>

`GET https://api.cartoncloud.com/tenants/{tenantId}/api_endpoint`

| URL Parameter | Description |
| --- | --- |
| tenantId | The UUID for the tenant to be accessed |

### Pagination <a id="pagination"></a>

For search requests and other end points which return multiple elements, data will be paged and the headers below returned.

Pagination uses the number of line items per page, specified using pageSize.

#### Request <a id="request-2"></a>

`GET https://api.cartoncloud.com/tenants/{tenantId}/api_endpoint?page=5&size=20`

| Query Parameter | Description | Default |
| --- | --- | --- |
| page | The page number to return results for | 1 |
| size | The number of elements per page | `varies with end point` |

#### Response <a id="response"></a>

| Header | Description |
| --- | --- |
| Total-Pages | Total number of pages of data that is available for the request |
| Page-Size | The number of elements per page |
| Page-Number | The page number for the returned results |
| Total-Elements | The total number of elements that is available for the request |
| Link | Links to other pages as [Web Links](https://tools.ietf.org/html/rfc5988) |

### Optional Fields <a id="optional-fields"></a>

- When including optional fields without data, use null .
- Do not use an empty string ("") as a substitute for null . Empty strings are used to represent a valid, empty string value.

## Customers <a id="customers"></a>

### Create Customer <a id="create-customer"></a>

Create a new customer

To perform this action, the API Client needs to have the “Add Customer” role. This can only be applied to internal clients.

#### Request <a id="request"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/customers" \
   -X POST \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Content-Type: application/json" \
   -d "{JSON AS BELOW}"
```

> Example Request JSON

```json
{
  "scope": "CUSTOMER",
  "references": {
    "code": "TEST_CODE"
  },
  "warehouses": [
    {...},
    {...}
  ],
  "name": "Test name",
  "email": "test-customer@cartoncloud.com.au",
  "telephone": "07777777"
}
```

`POST https://api.cartoncloud.com/tenants/{tenantId}/customers`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |

| JSON Property |  |  | Type | Required | Description |
| --- | --- | --- | --- | --- | --- |
| scope |  |  | String | - | `CUSTOMER` for customer |
| references | code |  | String | - | Code for the customer |
| warehouses |  |  | Array of [Warehouses](https://api-docs.cartoncloud.com#warehouse) | - | Warehouses for which the customer is used for. If not provided will be assigned to the `default` warehouse |
| name |  |  | String | Yes | Company name for the customer |
| email |  |  | String | - | Email address for the customer |
| telephone |  |  | String | - | Phone number for the customer |

#### Response <a id="response"></a>

> Example Response JSON

```json
{
  "enabled": true,
  "telephone": "7777777",
  "email": "test-customer@cartoncloud.com.au",
  "warehouses": [
    {...},
    {...}
  ],
  "scope": "CUSTOMER",
  "name": "Test name",
  "references": {
    "code": "TEST_CODE"
  },
  "id": "d9ca778f-d09c-422b-a422-f39597b9ad5d"
}
```

On success will return status code `201 Created` with the created order in the response body.
The data structure will be the same as in the above request, with the following additional properties.

| JSON Property |  | Type | Description |
| --- | --- | --- | --- |
| id |  | String | UUID for the customer |
| enabled |  | Boolean | If the Customer is enabled or not (defaults to true) |

### List Customers <a id="list-customers"></a>

Get a list of available customers

To perform this action, the API Client needs to have at least one of the following roles:

- Add Customer
- TMS Create Jobs
- WMS Create Jobs

#### Request <a id="request-2"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/customers" \
   -X GET \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}"
```

`GET https://api.cartoncloud.com/tenants/{tenantId}/customers`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |

#### Response <a id="response-2"></a>

> Example Response JSON

```json
[
  {
    "name": "Steam Chef Store",
    "id": "8f1a7728-c084-11e8-85b4-02a6cf3a00de"
  },
  {
    "name": "Alcohol Formula",
    "id": "8f1a78d3-c084-11e8-85b4-02a6cf3a00de"
  }
]
```

On success will return status code `200 OK` with the list of customers in the body.

### Get Customer <a id="get-customer"></a>

Retrieves a previously created customer

To perform this action, the API Client needs to have at least one of the following roles:

- Add Customer
- TMS Create Jobs
- WMS Create Jobs

#### Request <a id="request-3"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/customers/{id}" \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}"
```

`GET https://api.cartoncloud.com/tenants/{tenantId}/customers/{id}`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |
| id | UUID for the customer |

#### Response <a id="response-3"></a>

> Example Response JSON

```json
{
  "name": "Steam Chef Store",
  "id": "8f1a7728-c084-11e8-85b4-02a6cf3a00de"
}
```

On success will return status code `200 OK` with the customer in the response body.

## Inbound Orders (Purchase Orders) <a id="inbound-orders-purchase-orders"></a>

Inbound Orders are referred to as Purchase Orders within the CartonCloud Web App

### Create Inbound Order <a id="create-inbound-order"></a>

Create a new inbound order (purchase order)

To perform this action, the API Client needs to have the “WMS Create Job” role.

#### Request <a id="request"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/inbound-orders" \
   -X POST \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Content-Type: application/json" \
   -d "{JSON AS BELOW}"
```

> Example Request JSON

```json
{
  "type": "INBOUND",
  "status": "DRAFT",
  "references": {...},
  "customer": {...},
  "warehouse": {...},
  "details": {
    "urgent": true,
    "instructions": "",
    "arrivalDate": "2018-01-31"
  },
  "properties": {
    "myCustomField": "info"
  },
  "items": [
    {
      "properties": {
        "expiryDate": "2018-10-25",
        "batch": "AAAA"
      },
      "details": {
        "product": {...},
        "unitOfMeasure": {
          "type": "UNITS"
        }
      },
      "measures": {
        "quantity": 25
      }
      "status": "OK"
    },
    {
      "properties": {
        "expiryDate": "2018-10-22",
        "batch": "BBBB"
      },
      "details": {
        "product": {...},
        "unitOfMeasure": {
          "type": "CASES"
        }
      },
      "measures": {
        "quantity": 2
      },
      "status": "RECEIVED_DAMAGED"
    }
  ]
}
```

`POST https://api.cartoncloud.com/tenants/{tenantId}/inbound-orders`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |

| JSON Property |  |  | Type | Required | Description |
| --- | --- | --- | --- | --- | --- |
| type |  |  | String | - | The type of the order. This defaults to `INBOUND` when making a request to this endpoint |
| status |  |  | Status | - | Status for the order. Set to `DRAFT` to make it a draft order, otherwise will be assigned the initial status based on workflow. |
| references |  |  | [References](https://api-docs.cartoncloud.com#references) | Yes | References for the order |
| customer |  |  | [Customer](https://api-docs.cartoncloud.com#customer) | Yes | Customer for which the order is for |
| warehouse |  |  | [Warehouse](https://api-docs.cartoncloud.com#warehouse) | - | Warehouse for which the order is for. If not provided will be assigned to the `default` warehouse |
| details | urgent |  | Boolean | - | `true` for urgent orders |
|  | instructions |  | String | - | Special instructions related to the order |
|  | arrivalDate |  | String | - | The arrival date for the order |
| properties |  | `{custom}` | * | - | Custom fields relating to the order |
| items | properties | `{custom}` | * | - | Custom fields relating to the item (eg. batch, expiry, etc.) |
|  | details | product | [Product](https://api-docs.cartoncloud.com#product) | Yes | The product for the item |
|  |  | unitOfMeasure | [UnitOfMeasure](https://api-docs.cartoncloud.com#unitofmeasure) | - | The unit of measure the product will be created with. If not provided the default for the product will be used. |
|  | measures | quantity | Decimal | Yes | The quantity of the given product for the item |
|  | status |  | String | - | Status of the inbound item. Defaults to `OK` if not provided. Valid values: `OK`, `RECEIVED_DAMAGED`, `MISSING`, `QUARANTINE`, `DAMAGED_BY_CARRIER`, `DAMAGED`, `LOST` |

#### Response <a id="response"></a>

> Example Response JSON

```json
{
  "id": "318782ea-75b1-11e8-adc0-fa7ae01b9ebc",
  "type": "INBOUND",
  "status": "DRAFT",
  "references": {...},
  "customer": {...},
  "warehouse": {...},
  "details": {...},
  "properties": {...},
  "items": [...],
  "version": 1
}
```

On success will return status code 201 Created with the created order in the response body. A 228 Created with issues status code will be returned for orders created in a rejected status typically due to stock issues. The data structure will be the same as in the above request, with the following additional properties.

| JSON Property |  | Type | Description |
| --- | --- | --- | --- |
| id |  | string | UUID for the order |
| version |  | integer | [Version](https://api-docs.cartoncloud.com#entity-version) number for the entity |
| details | errors | Array of [Error References](https://api-docs.cartoncloud.com#error-reference) | If the order was created in a REJECTED status, additional information can be found in errors |

### Get Inbound Order <a id="get-inbound-order"></a>

Retrieves a previously created inbound order (purchase order)

To perform this action, the API Client needs to have the “WMS Create Job” role.

#### Request <a id="request-2"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/inbound-orders/{id}" \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}"
   -H "Prefer: return=no-items" \
```

`GET https://api.cartoncloud.com/tenants/{tenantId}/inbound-orders/{id}`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |
| id | UUID for the order |

| Header | Value | Description |
| --- | --- | --- |
| Prefer | return=no-items | If the preference header applied, items will not be included in the response. |

#### Response <a id="response-2"></a>

> Example Response JSON

```json
{
  "id": "318782ea-75b1-11e8-adc0-fa7ae01b9ebc",
  "status": "DRAFT",
  "references": {...},
  "customer": {...},
  "warehouse": {...},
  "details": {
    "urgent": true,
    "instructions": "",
    "arrivalDate": "2018-01-31",
    "parentId": "61d077f7-d035-44e4-8d3d-cdc6b84b298a",
    "hasChildren": false
  },
  "items": [...],
  "version": 1
}
```

> Example Response JSON with Prefer Header (return=no-items) provided

```json
{
  "id": "318782ea-75b1-11e8-adc0-fa7ae01b9ebc",
  "status": "DRAFT",
  "references": {...},
  "customer": {...},
  "warehouse": {...},
  "details": {...},
  "version": 1
}
```

On success will return status code `200 OK` with the order in the response body. 
For details on the response data refer to [create end point](https://api-docs.cartoncloud.com#create-inbound-order)

### Update Inbound Order <a id="update-inbound-order"></a>

Updates a previously created inbound order (purchase order)

NOT YET AVAILABLE - Estimated Availability TBD

DRAFT - Subject to change prior to final release

#### Request <a id="request-3"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/inbound-orders/{id}" \
   -X PUT \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "If-Match: {version}" \
   -H "Content-Type: application/json" \
   -d "{JSON AS BELOW}"
```

`GET https://api.cartoncloud.com/tenants/{tenantId}/inbound-orders/{id}`

For details on the request data refer to [response for create](https://api-docs.cartoncloud.com#create-inbound-order)

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |
| id | UUID for the order |

| Header | Description |
| --- | --- |
| If-Match | [Version](https://api-docs.cartoncloud.com#entity-version) number for the current entity |

#### Response <a id="response-3"></a>

> Example Response JSON

```json
{
  "id": "318782ea-75b1-11e8-adc0-fa7ae01b9ebc",
  "status": "DRAFT",
  "references": {...},
  "customer": {...},
  "warehouse": {...},
  "details": {...},
  "items": [...],
  "version": 2
}
```

On success will return status code `200 OK` with the updated order in the response body. 
For details on the response data refer to [response for create](https://api-docs.cartoncloud.com#create-inbound-order)

Depending on the status of the order not all updates will succeed

### Delete Inbound Order <a id="delete-inbound-order"></a>

Deletes an inbound order (purchase order)

To perform this action, the API Client needs to have the “WMS Create Job” role.

Deletion is only allowed for certain Purchase Order Statuses, which are configurable via the "Purchase Order Statuses on which overriding pre-existing Purchase Orders allowed on upload." Organization Setting: [Purchase Order Allowed Edit Organization Setting](https://help.cartoncloud.com/help/s/article/Organisation-Settings-Warehouse)

#### Request <a id="request-4"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/inbound-orders/{id}" \
   -X DELETE \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}"
```

`DELETE https://api.cartoncloud.com/tenants/{tenantId}/inbound-orders/{id}`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |
| id | UUID for the order |

#### Response <a id="response-4"></a>

On success will return status code `204 No Content` with an empty body.

### Search Inbound Orders <a id="search-inbound-orders"></a>

Search for previously created inbound orders (purchase order)

#### Request <a id="request-5"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/inbound-orders/search" \
   -X POST \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Content-Type: application/json" \
   -H "Prefer: return=minimal" \
   -d "{JSON AS BELOW}"
```

`POST https://api.cartoncloud.com/tenants/{tenantId}/inbound-orders/search`

> Example Request JSON

```json
{
    "condition": {
        "type": "OrCondition",
        "conditions": [
            {
                "type": "AndCondition",
                "conditions": [
                    {
                        "type": "TextComparisonCondition",
                        "field": {
                            "type": "ValueField",
                            "value": "reference"
                        },
                        "value": {
                            "type": "ValueField",
                            "value": "REF-1"
                        },
                        "method": "STARTS_WITH"
                    },
                    {
                        "type": "TextComparisonCondition",
                        "field": {
                            "type": "ValueField",
                            "value": "customerName"
                        },
                        "value": {
                            "type": "ValueField",
                            "value": "Customer A"
                        },
                        "method": "EQUAL_TO"
                    }
                ]
            }
        ]
    }
}
```

| JSON Property |  | Type | Description |
| --- | --- | --- | --- |
| condition | type | string | Wrap level condition ( OrCondition / AndCondition ) |
|  | conditions | Array of [Search Conditions](https://api-docs.cartoncloud.com#search-condition-types) | All conditions in the array will be combined by the wrap level condition specified in the "type" field |

| Header | Value | Description |
| --- | --- | --- |
| Prefer | return=minimal | Switch the response into minimal representation. If preference applied the Preference-Applied response header will be returned |

Currently these keys are available for search (/conditions/field/value):

| Name | Type |
| --- | --- |
| reference | String |
| customerName | String |
| customerId | String |
| arrivalDate | String |
| createdDate | String |

Condition nesting is possible for complex search. For this purpose the inner condition object can be provided instead of the Search Conditions array (see example)

#### Response <a id="response-5"></a>

> Example Response JSON with Prefer Header provided

```json
[
    {
        "id": "fe84f560-515d-40d8-9760-0c222d7bfde7"
    },
    {
        "id": "4c1c1721-27c8-4bec-a7b7-49c386e0bee7"
    }
]
```

> Example Response JSON without Prefer Header

```json
[
  {
    "details": {...},
    "items": [
      {...},
      {...}
    ],
    "type": "INBOUND",
    "status": "ALLOCATED",
    "customer": {
      "enabled": true,
      "name": "Customer A",
      "id": "ef50364f-ee15-4d8f-b938-3f77effedfe3"
    },
    "warehouse": {
      "enabled": true,
      "name": "Default",
      "id": "bbe1b844-f016-11ec-a36a-0296022725e2"
    },
    "version": 2,
    "references": {
      "customer": "REF-1",
      "numericId": "1"
    },
    "id": "aa031748-b085-4c77-bec4-bdb91cd6c6db"
  },
  {
    "details": {...},
    "items": [
      {...},
      {...}
    ],
    "type": "INBOUND",
    "status": "VERIFIED",
    "customer": {
      "enabled": true,
      "name": "Customer A",
      "id": "ef50364f-ee15-4d8f-b938-3f77effedfe3"
    },
    "warehouse": {
      "enabled": true,
      "name": "Default",
      "id": "bbe1b844-f016-11ec-a36a-0296022725e2"
    },
    "version": 2,
    "references": {
      "customer": "REF-12",
      "numericId": "2"
    },
    "id": "08619bd8-592b-4837-89f6-2c36c9ccc3f6"
  }
]
```

On success will return status code `200 Success` with an array of found inbound orders in response body. The array can be paged (see [Pagination](https://api-docs.cartoncloud.com#pagination))

## Outbound Orders (Sale Orders) <a id="outbound-orders-sale-orders"></a>

Outbound Orders are referred to as Sale Orders within the CartonCloud Web App

### Create Outbound Order <a id="create-outbound-order"></a>

Create a new outbound order (sale order)

To perform this action, the API Client needs to have the “WMS Create Jobs” role.

NB If the customer is configured with the "Automatically Generate a Consignment 
from a Sale Order" setting, "Yes, on Sale Order Import or Pack Completion", then the API Client will also require
the “TMS Create Jobs” role.

#### Request <a id="request"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/outbound-orders" \
   -X POST \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Content-Type: application/json" \
   -d "{JSON AS BELOW}"
```

> Example Request JSON

```json
{
  "type": "OUTBOUND",
  "references": {...},
  "customer": {...},
  "warehouse": {...},
  "details": {
    "urgent": true,
    "instructions": "",
    "collect": {
      "requiredDate": "2018-06-21"
    },
    "deliver": {
      "address": {...},
      "method": { 
        "type": "SHIPPING",
        "requestedService": "Express"
      },
      "instructions": "Leave by front door",
      "requiredDate": "2018-06-22",
      "cashPaymentAmount": {...}
    },
    "invoiceValue": {...},
    "allowSplitting": true
  },
  "properties": {
    "myCustomField": "info"
  },
  "items": [
    {
      "properties": {
        "expiryDate": "2018-10-25",
        "batch": "AAAA"
      },
      "details": {
        "product": {...},
        "unitOfMeasure": {
          "type": "UNITS"
        },
        "approximateUnitPrice": {
          "amount": 2.5,
          "currency": "USD"
        }
      },
      "measures": {
        "quantity": 25
      }
    },
    {
      "properties": {
        "expiryDate": "2018-10-22",
        "batch": "ABC 123"
        "sop_custom_field_1": "1"
      },
      "details": {
        "product": {...},
        "unitOfMeasure": {
          "type": "CASES"
        },
        "approximateUnitPrice": {
          "amount": 10,
          "currency": "USD"
        }
      },
      "measures": {
        "quantity": 2
      }
    }
  ]
}
```

`POST https://api.cartoncloud.com/tenants/{tenantId}/outbound-orders`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |

| JSON Property |  |  | Type | Required | Description |
| --- | --- | --- | --- | --- | --- |
| type |  |  | String | - | The type of the order. This defaults to `OUTBOUND` when making a request to this endpoint |
| references |  |  | [References](https://api-docs.cartoncloud.com#references) | Yes | References for the order |
| customer |  |  | [Customer](https://api-docs.cartoncloud.com#customer) | Yes | Customer for which the order is for |
| warehouse |  |  | [Warehouse](https://api-docs.cartoncloud.com#warehouse) | - | Warehouse for which the order is for. If not provided will be assigned to the `default` warehouse |
| details | urgent |  | Boolean | - | `true` for urgent orders |
|  | instructions |  | String | - | Packing instructions |
|  | collect | requiredDate | Date | - | Date the order should be shipped or collected from warehouse |
|  | deliver | address | [Address](https://api-docs.cartoncloud.com#address) | Yes | Address to deliver order to |
|  |  | method | [DeliveryMethod](https://api-docs.cartoncloud.com#deliverymethod) | - | The type of method used to transfer order items to a customer |
|  |  | instructions | String | - | Delivery instructions |
|  |  | requiredDate | Date | - | Date the order should be delivered |
|  |  | cashPaymentAmount | [Money](https://api-docs.cartoncloud.com#money) | - | Cash on delivery amount to be paid |
|  | invoiceValue |  | [Money](https://api-docs.cartoncloud.com#money) | - | Total invoice value for the order. Must be greater than or equal to 0.00. Supports currencies other than the tenant default currency. Will use the tenant default currency if not provided. |
|  | allowSplitting |  | Boolean | - | `false` for the orders prevented from being split. Default is `true` |
| properties |  | `{custom}` | * | - | Custom fields relating to the order |
| items | properties | `{custom}` | Purchase Order Product (POP Custom Field) | - | Custom fields relating to the item (eg. batch, expiry, etc.) |
|  |  | `{sop_custom_field_1}` | Sale Order Product (SOP Custom Field) |  | Custom fields relating to the sale order product line items (eg. line ID, product ID) |
|  | details | product | [Product](https://api-docs.cartoncloud.com#product) | Yes | Product for the item |
|  |  | unitOfMeasure | [UnitOfMeasure](https://api-docs.cartoncloud.com#unitofmeasure) | - | The unit of measure the product will be created with. If not provided the default for the product will be used. |
|  |  | approximateUnitPrice | [Money](https://api-docs.cartoncloud.com#money) | - | The approximate price for the unit provided in `/details/unitOfMeasure`. Both amount and currency must be provided when this field is included. |
|  | measures | quantity | Decimal | Yes | The quantity of the given product for the item |
| timestamps | created |  | [Timestamp](https://api-docs.cartoncloud.com#timestamp) | - | Timestamp when the order was created |
|  | modified |  | [Timestamp](https://api-docs.cartoncloud.com#timestamp) | - | Timestamp when the order was last modified |
|  | packed |  | [Timestamp](https://api-docs.cartoncloud.com#timestamp) | - | Timestamp when the order was packed |
|  | dispatched |  | [Timestamp](https://api-docs.cartoncloud.com#timestamp) | - | Timestamp when the order was dispatched |

#### Response <a id="response"></a>

> Example Response JSON

```json
{
    "id": "fb5b56f6-a68e-11e8-98d0-529269fb1459",
    "type": "OUTBOUND",
    "references": {...},
    "customer": {...},
    "warehouse": {...},
    "details": {
        "urgent": true,
        "instructions": "",
        "collect": {...},
        "deliver": {...},
        "invoiceValue": {...},
        "errors": [
            {
                "message": "Ice Cream (IC-123) x 25 UNITS - Product not found",
                "isResolved": false
            }
        ],
        "allowSplitting": true
    },
    "status": "REJECTED",
    "properties": {...},
    "items": [...],
    "version": 1,
    "timestamps": {
        "created": {
            "time": "2025-04-10T12:10:04+10:00"
        },
        "modified": {
            "time": "2025-07-07T10:06:24+10:00"
        }
    }
}
```

On success will return status code `201 Created` with the created order in the response body.
A `228 Created with issues` status code will be returned for outbound orders created in a rejected status typically due to stock issues. 
The data structure will be the same as in the above request, with the following additional properties.

| JSON Property |  | Type | Description |
| --- | --- | --- | --- |
| id |  | string | UUID for the order |
| version |  | integer | [Version](https://api-docs.cartoncloud.com#entity-version) number for the entity |
| status |  | string | Status of the outbound order (DRAFT / AWAITING_STOCK / AWAITING_PICK_AND_PACK / PACKING_IN_PROGRESS / PICKED / PACKED / DISPATCHED / REJECTED) |
| details | errors | Array of [Error References](https://api-docs.cartoncloud.com#error-reference) | If the order was created in a REJECTED status, additional information can be found in errors |

This endpoint has been rate limited to 30 requests per minute per user (i.e. no more than 1 request every 2 seconds).

### Get Outbound Order <a id="get-outbound-order"></a>

Retrieves a previously created outbound order (sale order)

To perform this action, the API Client needs to have the “WMS Create Job” role.

#### Request <a id="request-2"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/outbound-orders/{id}" \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}"
```

`GET https://api.cartoncloud.com/tenants/{tenantId}/outbound-orders/{id}`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |
| id | UUID for the order |

#### Response <a id="response-2"></a>

> Example Response JSON

```json
{
    "id": "fb5b56f6-a68e-11e8-98d0-529269fb1459",
    "type": "OUTBOUND",
    "references": {...},
    "customer": {...},
    "warehouse": {...},
    "details": {...}
    "status": "DISPATCHED",
    "properties": {...},
    "items": [...],
    "version": 5
}
```

On success will return status code `200 OK` with the order in the response body. 
For details on the response data refer to [response for create](https://api-docs.cartoncloud.com#create-outbound-order)

### Update Outbound Order (sale order) <a id="update-outbound-order-sale-order"></a>

Updates a previously created outbound order

To perform this action, the API Client needs to have the “WMS Create Job” role.

NOT YET AVAILABLE - Estimated Availability TBD

DRAFT - Subject to change prior to final release

#### Request <a id="request-3"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/outbound-orders/{orderId}" \
   -X PUT \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "If-Match: {version}" \
   -H "Content-Type: application/json" \
   -d "{JSON AS BELOW}"
```

`GET https://api.cartoncloud.com/tenants/{tenantId}/outbound-orders/{id}`

For details on the request data refer to [response for create](https://api-docs.cartoncloud.com#create-outbound-order)

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |
| id | UUID for the order |

| Header | Description |
| --- | --- |
| If-Match | [Version](https://api-docs.cartoncloud.com#entity-version) number for the current entity |

#### Response <a id="response-3"></a>

> Example Response JSON

```json
{
  "id": "fb5b56f6-a68e-11e8-98d0-529269fb1459",
  "status": "DRAFT",
  "references": {...},
  "customer": {...},
  "warehouse": {...},
  "details": {...},
  "items": [...],
  "version": 2
}
```

On success will return status code `200 OK` with the updated order in the response body. 
For details on the response data refer to [create end point](https://api-docs.cartoncloud.com#create-outbound-order)

Depending on the status of the order not all updates will succeed

### Delete Outbound Order <a id="delete-outbound-order"></a>

Deletes an outbound order (sale order)

To perform this action, the API Client needs to have the “WMS Create Job” role.

Deletion is only allowed for certain Sale Order Statuses, which are configurable via the "Sale Order Statuses on which overriding a pre-existing Sale Order (or deleting an existing Sale Order) is allowed" Organization Setting: [Sale Order Allowed Edit/Delete Organization Setting](https://help.cartoncloud.com/help/s/article/Organisation-Settings-Warehouse)

#### Request <a id="request-4"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/outbound-orders/{id}" \
   -X DELETE \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}"
```

`DELETE https://api.cartoncloud.com/tenants/{tenantId}/outbound-orders/{id}`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |
| id | UUID for the order |

#### Response <a id="response-4"></a>

On success will return status code `204 No Content` with an empty body.

### Search Outbound Orders <a id="search-outbound-orders"></a>

Search for previously created outbound orders (sale order)

#### Request <a id="request-5"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/outbound-orders/search" \
   -X POST \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Content-Type: application/json" \
   -H "Prefer: return=minimal" \
   -d "{JSON AS BELOW}"
```

`POST https://api.cartoncloud.com/tenants/{tenantId}/outbound-orders/search`

> Example Request JSON

```json
{
    "condition": {
        "type": "OrCondition",
        "conditions": [
            {
                "type": "AndCondition",
                "conditions": [
                    {
                        "type": "TextComparisonCondition",
                        "field": {
                            "type": "ValueField",
                            "value": "reference"
                        },
                        "value": {
                            "type": "ValueField",
                            "value": "REF-1"
                        },
                        "method": "STARTS_WITH"
                    },
                    {
                        "type": "TextComparisonCondition",
                        "field": {
                            "type": "ValueField",
                            "value": "customerName"
                        },
                        "value": {
                            "type": "ValueField",
                            "value": "Customer A"
                        },
                        "method": "EQUAL_TO"
                    }
                ]
            }
        ]
    }
}
```

| JSON Property |  | Type | Description |
| --- | --- | --- | --- |
| condition | type | string | Wrap level condition ( OrCondition / AndCondition ) |
|  | conditions | Array of [Search Conditions](https://api-docs.cartoncloud.com#search-condition-types) | All conditions in the array will be combined by the wrap level condition specified in the "type" field |

| Header | Value | Description |
| --- | --- | --- |
| Prefer | return=minimal | Switch the response into minimal representation. If preference applied the Preference-Applied response header will be returned |

Currently these keys are available for search. The field parameter can use either JsonField or ValueField (deprecated):

| ValueField value | JsonField pointer | Type |
| --- | --- | --- |
| reference | /references/customer | string |
| customerName | /customer/name | string |
| customerId | /customer/id | string |
|  | /timestamps/created/time | string (ISO 8601 format) |
|  | /timestamps/modified/time | string (ISO 8601 format) |
|  | /timestamps/dispatched/time | string (ISO 8601 format) |
|  | /timestamps/packed/time | string (ISO 8601 format) |

Condition nesting is possible for complex search. For this purpose the inner condition object can be provided instead of the Search Conditions array (see example)

#### Response <a id="response-5"></a>

> Example Response JSON with Prefer Header provided

```json
[
    {
        "id": "fe84f560-515d-40d8-9760-0c222d7bfde7"
    },
    {
        "id": "4c1c1721-27c8-4bec-a7b7-49c386e0bee7"
    }
]
```

> Example Response JSON without Prefer Header

```json
[
    {
      "type": "OUTBOUND",
      "references": {
          "customer": "REF-123"
      },
      "customer": {
          "enabled": true,
          "name": "Customer A",
          "references": {
              "code": "CustomerA"
          },
          "id": "c3b1a598-c085-11e8-85b4-02a6cf3a00de"
      },
      "version": 17,
      "warehouse": {...},
      "details": {...},
      "properties": {...},
      "status": "PACKING_IN_PROGRESS",
      "items": [
        {...},
        {...}
      ],
      "id": "fe84f560-515d-40d8-9760-0c222d7bfde7"
    },
    {
      "type": "OUTBOUND",
      "references": {
          "customer": "REF-124"
      },
      "customer": {
          "enabled": true,
          "name": "Customer A",
          "references": {
              "code": "CustomerA"
          },
          "id": "c3b1a598-c085-11e8-85b4-02a6cf3a00de"
      },
      "version": 17,
      "warehouse": {...},
      "details": {...},
      "properties": {...},
      "status": "DRAFT",
      "items": [
        {...}
      ],
      "id": "4c1c1721-27c8-4bec-a7b7-49c386e0bee7"
    }
]
```

On success will return status code `200 Success` with an array of found outbound orders in response body. The array can be paged (see [Pagination](https://api-docs.cartoncloud.com#pagination))

### Create Outbound Document <a id="create-outbound-document"></a>

Attach a document to an existing outbound order.

To perform this action, the API Client needs to have at least one of the following roles:

- Add Customer
- Internal Field Access
- TMS Add/Edit Product
- TMS Create Jobs
- WMS Edit Product
- WMS Create Jobs

Note, for API Clients with Customer-Role access, you need to have allowed the Customer to upload documents: [Customer Invoice or Document Upload](https://help.cartoncloud.com/kb2/web-app-page-specific-support/administrator-pages/contacts/customers/edit-customer-or-customer-settings/edit-customer-warehouse-management/customer-sale-order-settings#CustomerSaleOrderSettings-CustomerInvoiceorDocumentUpload)

#### Request <a id="request-6"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/outbound-orders/{outboundOrderId}/documents" \
   -X POST \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Content-Type: application/json" \
   -d "{JSON AS BELOW}"
```

> Example Request JSON

```json
{
  "type": "OUTBOUND_ORDER_INVOICE",
  "content": {
    "name": "Invoice.pdf",
    "data": "JVBERi0xLjcKJeLjz9MKNSdCAzOCAwIFIKL0...{base64 encoded file content}"
  }
}
```

`POST https://api.cartoncloud.com/tenants/{tenantId}/outbound-orders/{outboundOrderId}/documents`

| JSON Property |  |  | Type | Required | Description |
| --- | --- | --- | --- | --- | --- |
| type |  |  | String | Yes | OUTBOUND_ORDER_INVOICE |
| content | name |  | String | Yes | Name of the uploaded file |
| data |  | String | Yes | Base64-encoded content of the file |  |

#### Response <a id="response-6"></a>

> Example Response JSON

```json
{
  "content": {
    "name": "Invoice.pdf",
    "data": "JVBERi0xLjcKJeLjz9MKNSdCAzOCAwIFIKL0...{base64 encoded file content}"
  },
  "type": "OUTBOUND_ORDER_INVOICE",
  "owner": {
    "type": "OUTBOUND",
    "id": "2df05c03-8f11-4cba-b78d-7a6f34d34c8b"
  },
  "id": "975487fb-833d-41de-9ac2-114d8e6cb9e2"
}
```

On success will return status code `201 Created` with the created document details in the response body.

### Get Outbound Document <a id="get-outbound-document"></a>

Retrieves a previously created outbound order document

To perform this action, the API Client needs to have at least one of the following roles:

- Add Customer
- Internal Field Access
- TMS Add/Edit Product
- TMS Create Jobs
- WMS Edit Product
- WMS Create Jobs

#### Request <a id="request-7"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/outbound-orders/{outboundOrderId}/documents/{id}" \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}"
```

`GET https://api.cartoncloud.com/tenants/{tenantId}/outbound-orders/{outboundOrderId}/documents/{id}`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |
| outboundOrderId | UUID for the order |
| id | UUID for the invoice |

#### Response <a id="response-7"></a>

> Example Response JSON

```json
{
  "content": {
    "name": "Invoice.pdf",
    "data": "JVBERi0xLjcKJeLjz9MKNSdCAzOCAwIFIKL0...{base64 encoded file content}"
  },
  "type": "OUTBOUND_ORDER_INVOICE",
  "owner": {
    "type": "OUTBOUND",
    "id": "2df05c03-8f11-4cba-b78d-7a6f34d34c8b"
  },
  "id": "975487fb-833d-41de-9ac2-114d8e6cb9e2"
}
```

On success will return status code `200 Success` with the document details in the response body.

### Download Outbound Document <a id="download-outbound-document"></a>

Download a previously created outbound order document

To perform this action, the API Client needs to have at least one of the following roles:

- Add Customer
- Internal Field Access
- TMS Add/Edit Product
- TMS Create Jobs
- WMS Edit Product
- WMS Create Jobs

#### Request <a id="request-8"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/outbound-orders/{outboundOrderId}/documents/{id}/download" \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}"
```

`GET https://api.cartoncloud.com/tenants/{tenantId}/outbound-orders/{outboundOrderId}/documents/{id}/download`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |
| outboundOrderId | UUID for the order |
| id | UUID for the invoice |

#### Response <a id="response-8"></a>

On success will return the document file content

### List Outbound Documents <a id="list-outbound-documents"></a>

Get a list of documents for an existing outbound order

To perform this action, the API Client needs to have at least one of the following roles:

- Add Customer
- Internal Field Access
- TMS Add/Edit Product
- TMS Create Jobs
- WMS Edit Product
- WMS Create Jobs

#### Request <a id="request-9"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/outbound-orders/{outboundOrderId}/documents" \
   -X GET \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Prefer: return=minimal" \
   -H "Content-Type: application/json" 
```

`GET https://api.cartoncloud.com/tenants/{tenantId}/outbound-orders/{outboundOrderId}/documents`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |
| outboundOrderId | UUID for the outbound order |

| Header | Value | Description |
| --- | --- | --- |
| Prefer | return=minimal | Switch the response into minimal representation. If preference applied the Preference-Applied response header will be returned |

#### Response <a id="response-9"></a>

> Example Response JSON

```json
[
  {
    "content": {
      "name": "Invoice.pdf"
    },
    "type": "OUTBOUND_ORDER_INVOICE",
    "id": "1b1f5eab-007e-4fcc-a7b6-0583c830ad56"
  },
  {
    "content": {
      "name": "Invoice2.pdf"
    },
    "type": "OUTBOUND_ORDER_INVOICE",
    "id": "975487fb-833d-41de-9ac2-114d8e6cb9e2"
  },
  {
    "content": {
      "name": "Invoice3.png"
    },
    "type": "OUTBOUND_ORDER_INVOICE",
    "id": "e528b2f1-60f6-441d-aac3-1f0c123984b1"
  }
]
```

On success will return status code `200 Success` with an array of found invoices in response body. The array can be paged (see [Pagination](https://api-docs.cartoncloud.com#pagination))

## Warehouse Products <a id="warehouse-products"></a>

### Create Warehouse Product <a id="create-warehouse-product"></a>

Create a new warehouse product

To perform this action, the API Client needs to have the “WMS Add Product” role.

#### Warehouse Product <a id="warehouse-product"></a>

#### Request <a id="request"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/warehouse-products" \
   -X POST \
   -H "Accept-Version: 8" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Content-Type: application/json" \
   -d "{JSON AS BELOW}"
```

`POST https://api.cartoncloud.com/tenants/{tenantId}/warehouse-products`

> Example Warehouse Product Request JSON

```json
{
  "scope": "WAREHOUSE",
  "references": {...},
  "customer": {...},
  "type": "FROZEN",
  "name": "Ice Cream",
  "description": "Chocolate ice cream 4L",
  "details": {
    "variableWeight": true,
    "storage": {
      "chargeMethod": "PER_LOCATION"
    },
    "inbound": {
      "initialStatus": "QC"
    },
    "stockSelection": {
      "method": "FEFO",
      "secondaryMethod": "MINIMISE_STORAGE",
      "strict": true,
      "expiryThresholdDays": 10
    },
    "active": true,
    "countryOfOrigin": {
      "name": "Australia",
      "iso2Code": "AU",
      "iso3Code": "AUS"
    },
    "harmonizedSystemCode": "2105.00.10"
  },
  "itemPropertyRequirements": {
    "expiry": "REQUIRED",
    "batch": "OPTIONAL"
  },
  "defaultUnitOfMeasure": "cartons",
  "unitOfMeasures": {
    "units": {
      "baseQty": 1,
      "weight": 1.2,
      "barcode": "BARCODEUNITS",
      "length": 10.234,
      "width": 3.98,
      "height": 5.1,
      "isDirectlyShippable": true
    },
    "cartons": {
      "baseQty": 10
    },
    "pallets": {
      "baseQty": 100,
      "barcode": "BARCODEPALLETS",
      "length": 9.01,
      "width": 7.62,
      "height": 8.0,
      "isDirectlyShippable": false
    }
  },
  "notifications": [
    {
      "type": "STOCK_EXPIRY",
      "thresholdDays": 20
    },
    {
      "type": "STOCK_LOW",
      "thresholdCount": 10
    }
  ]
}
```

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |

| JSON Property |  |  | Type | Required | Description |
| --- | --- | --- | --- | --- | --- |
| scope |  |  | String | Yes | `WAREHOUSE` for warehousing product |
| type |  |  | String | Yes | Product types are defined per tenant |
| references |  |  | [References](https://api-docs.cartoncloud.com#references) | Yes | References for the product |
| customer |  |  | [Customer](https://api-docs.cartoncloud.com#customer) | Yes | Customer for which the product is for |
| name |  |  | String | Yes | Short name for the product |
| description |  |  | String | - | Full product description |
| details | variableWeight |  | Boolean | - | `true` for variable weight products |
|  | storage | chargeMethod | String | - | `PER_LOCATION`, `` |
|  | inbound | initialStatus | String | - | Initial product status when first received |
|  | stockSelection | method | String | - | `FEFO`, `FIFO` |
|  |  | secondaryMethod | String | - | `MINIMISE_STORAGE` |
|  |  | strict | Boolean | - | Strict selection method |
|  |  | expiryThresholdDays | Integer | - | Expiry threshold days |
|  | active |  | Boolean | - | `true` if the product is active |
|  | countryOfOrigin |  | [Country](https://api-docs.cartoncloud.com#country) | - | Country of origin for the product.   Available from API version 7. |
|  | harmonizedSystemCode |  | String | - | Harmonized System (HS) Code for product classification used in international trade.   Available from API version 7.      Validation Rules:   • Only accepts numeric characters (0-9) and period (.) characters   • Period characters are automatically removed prior to saving   • Must contain at least 6 numeric characters |
| itemPropertyRequirements | `{custom}` |  | String | - | `REQUIRED`, `OPTIONAL` |
| defaultUnitOfMeasure |  |  | String | Yes |  |
| unitOfMeasures | `{unit of measure}` | baseQty | Decimal | Yes | Quantity of base unit of measure per one of this unit of measure |
|  |  | weight | Decimal | - | Weight per unit of measure |
|  |  | barcode | String | - | If the base unit of measure barcode is not provided, the product code will automatically be applied as the barcode for the base unit of measure. |
|  |  | length | Decimal | - | Length per unit of measure |
|  |  | width | Decimal | - | Width per unit of measure |
|  |  | height | Decimal | - | Height per unit of measure |
|  |  | isDirectlyShippable | Boolean | - | `true` if the unit of measure is directly shippable |
| notifications |  |  |  | - | List of notifications applicable to this product |
|  | type |  | String | Yes | Notification type |
|  | * |  | * | * | Varies depending on notification |

API version 8 can be requested by providing the header `Accept-Version: 8`.

If a base unit of measure supplied with a length, width and height then the Product volume will be the multiplication of these values.

#### Response <a id="response"></a>

> Example Response JSON

```json
{
  "id": "318782ea-75b1-11e8-adc0-fa7ae01b9ebc",
  ...
}
```

On success will return status code `201 Created` with the created product in the response body. 
The data structure will be the same as in the above request, with the following additional id property.

| JSON Property | Description |
| --- | --- |
| id | UUID for the product |

Adding barcodes via API is not currently supported. This can be done by the tenant using the Product Import process.

### Get Product <a id="get-product"></a>

Retrieves a previously created product

To perform this action, the API Client needs to have at least one of the following roles:

- WMS Add Product
- WMS Edit Product

#### Request <a id="request-2"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/warehouse-products/{id}" \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}"
```

`GET https://api.cartoncloud.com/tenants/{tenantId}/warehouse-products/{id}`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |
| id | UUID for the product |

#### Response <a id="response-2"></a>

> Example Response JSON

```json
{
  "id": "fb5b56f6-a68e-11e8-98d0-529269fb1459",
  "name": "Ice Cream",
  "type": "Chilled",
  "references": {...},
  "customer": {...},
  "details": {...},
  "itemPropertyRequirements": {...},
  "unitOfMeasures": {...}
}
```

On success will return status code `200 OK` with the product in the response body. 
For details on the response data refer to [response for create](https://api-docs.cartoncloud.com#create-product)

### Update Product (PUT) <a id="update-product-put"></a>

Deprecated as of version 8. Use [Partial Product Update (PATCH)](https://api-docs.cartoncloud.com#partial-product-update-patch) instead.

Updates a previously created product

To perform this action, the API Client needs to have the “WMS Edit Product” role.

#### Request <a id="request-3"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/warehouse-products/{id}" \
   -X PUT \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Content-Type: application/json" \
   -d "{JSON AS BELOW}"
```

`PUT https://api.cartoncloud.com/tenants/{tenantId}/warehouse-products/{id}`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |
| id | UUID for the product |

> Example Request JSON

For details on the request data refer to [response for create](https://api-docs.cartoncloud.com#create-product)

#### Response <a id="response-3"></a>

> Example Response JSON

```json
{
  "id": "fb5b56f6-a68e-11e8-98d0-529269fb1459",
  "name": "Ice Cream",
  "type": "Chilled",
  "references": {...},
  "customer": {...},
  "details": {...},
  "itemPropertyRequirements": {...},
  "unitOfMeasures": {...}
}
```

In case of the defaultUnitOfMeasure update conversion rate 1:1 will be applied

On success will return status code `200 OK` with the updated product in the response body.
For details on the response data refer to [response for create](https://api-docs.cartoncloud.com#create-product)

### Partial Product Update (PATCH) <a id="partial-product-update-patch"></a>

Updates a previously created product

To perform this action, the API Client needs to have the “WMS Edit Product” role.

#### Request <a id="request-4"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/warehouse-products/{id}" \
   -X PATCH \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Content-Type: application/json" \
   -d "{JSON AS BELOW}"
```

`PATCH https://api.cartoncloud.com/tenants/{tenantId}/warehouse-products/{id}`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |
| id | UUID for the product |

> Example Request JSON

```json
{
    {
        "op": "remove",
        "path": "/itemPropertyRequirements/expiry"
    },
    {
        "op": "replace",
        "path": "/name",
        "value": "Strawberry Ice Cream"
    },
    {
        "op": "add",
        "path": "/notifications/-",
        "value":
        {
           "type": "STOCK_LOW",
           "thresholdCount": 30
        }
    }
}
```

#### Response <a id="response-4"></a>

> Example Response JSON

```json
{
  "id": "fb5b56f6-a68e-11e8-98d0-529269fb1459",
  "name": "Strawberry Ice Cream",
  "type": "Chilled",
  "references": {...},
  "customer": {...},
  "details": {...},
  "itemPropertyRequirements": {...},
  "unitOfMeasures": {...}
}
```

On success will return status code `200 OK` with the updated product in the response body.
For details on the response data refer to [response for create](https://api-docs.cartoncloud.com#create-product)

In case of the defaultUnitOfMeasure update conversion rate 1:1 will be applied

Implemented patch operations - add, replace, remove

Some paths values cannot be changed (ex. /id, /customer/*)

For some paths the remove operation results as default value setting (ex. /details/stockSelection)

Partial array updates (ex. /notificatons/0) are not permitted. Alternatively you can override entire array or append a new value using "-" symbol (ex. /notificatons/-)

For more json patch details please see https://tools.ietf.org/html/rfc6902

### Search Warehouse Products <a id="search-warehouse-products"></a>

Search for previously created warehouse products

#### Request <a id="request-5"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/warehouse-products/search" \
   -X POST \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Content-Type: application/json" \
   -d "{JSON AS BELOW}"
```

`POST https://api.cartoncloud.com/tenants/{tenantId}/warehouse-products/search`

> Example Request JSON

```json
{
    "condition": {
        "type": "OrCondition",
        "conditions": [
            {
                "type": "AndCondition",
                "conditions": [
                    {
                        "type": "TextComparisonCondition",
                        "field": {
                            "type": "JsonField",
                            "pointer": "/name"
                        },
                        "value": {
                            "type": "ValueField",
                            "value": "Ice Cream"
                        },
                        "method": "CONTAINS"
                    },
                    {
                        "type": "TextComparisonCondition",
                        "field": {
                            "type": "JsonField",
                            "pointer": "/customer/id"
                        },
                        "value": {
                            "type": "ValueField",
                            "value": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6"
                        },
                        "method": "EQUAL_TO"
                    }
                ]
            }
        ]
    }
}
```

| JSON Property |  | Type | Description |
| --- | --- | --- | --- |
| condition | type | string | Wrap level condition ( OrCondition / AndCondition ) |
|  | conditions | Array of [Search Conditions](https://api-docs.cartoncloud.com#search-condition-types) | All conditions in the array will be combined by the wrap level condition specified in the "type" field |

Currently these keys are available for search:

| JsonField pointer | Type |
| --- | --- |
| /id | string |
| /code | string |
| /name | string |
| /customer/id | string |
| /customer/name | string |
| /details/active | boolean |
| /timestamps/created/time | string (ISO 8601 format) |
| /timestamps/modified/time | string (ISO 8601 format) |

Condition nesting is possible for complex search. For this purpose the inner condition object can be provided instead of the Search Conditions array (see example)

#### Response <a id="response-5"></a>

> Example Response JSON

```json
[
    {
        "id": "318782ea-75b1-11e8-adc0-fa7ae01b9ebc",
        "scope": "WAREHOUSE",
        "name": "Ice Cream",
        "type": "FROZEN",
        "description": "Chocolate ice cream 4L",
        "references": {...},
        "customer": {...},
        "details": {...},
        "itemPropertyRequirements": {...},
        "unitOfMeasures": {...}
    },
    {
        "id": "4c1c1721-27c8-4bec-a7b7-49c386e0bee7",
        "scope": "WAREHOUSE",
        "name": "Ice Cream Coffee",
        "type": "FROZEN",
        "references": {...},
        "customer": {...},
        "details": {...},
        "itemPropertyRequirements": {...},
        "unitOfMeasures": {...}
    }
]
```

On success will return status code `200 Success` with an array of found warehouse products in response body. The array can be paged (see [Pagination](https://api-docs.cartoncloud.com#pagination))

## Consignments <a id="consignments"></a>

### Create Consignment <a id="create-consignment"></a>

Create a new consignment

To perform this action, the API Client needs to have the “TMS Create Jobs” role.

#### Request <a id="request"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/consignments" \
   -X POST \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Content-Type: application/json" \
   -d "{JSON AS BELOW}"
```

> Example Request JSON

```json
{
  "references": {...},
  "customer": {...},
  "warehouse": {...},
  "user": {...},
  "details": {
    "collect": {
      "address": {...},
    },
    "deliver": {
      "address": {...},
      "instructions": "Leave by front door",
      "requiredDate": "2018-06-22",
      "cashPaymentAmount": {...}
    }
    "invoiceValue": {...},
    "manifest": {...},
    "type": {...},
    "authorityToLeave": {...},
    "authorityToLeaveInstructions": {...},
    "deliveryRun": {...},
    "runsheet": {...},
    "tracking": {
      "companyName": "Tracking company",
      "url": "https://www.example.com/path"
    }
  },
  "properties": {
    "serviceType": "EXPRESS",
    "myCustomField": "info"
  },
  "measures": {
    "hours": 5,
    "distance": {
      "value": 100
    }
  },
  "items": [
    {
      "properties": {
        "description": "misc equipment"
      },
      "measures": {
        "pallets": 2,
        "weight": 120,
        "quantity": 10
      }
    },
    {
      "measures": {
        "pallets": 3,
        "weight": 160
      },
      "details": {
        "product": {
          "references": {
            "code": "DRUM"
          }
        }
      }
    }
  ]
}
```

`POST https://api.cartoncloud.com/tenants/{tenantId}/consignments`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |

| JSON Property |  |  | Type | Required | Description |
| --- | --- | --- | --- | --- | --- |
| type |  |  | String | - | The type of the order. This defaults to `CONSIGNMENT` when making a request to this endpoint |
| references |  |  | [References](https://api-docs.cartoncloud.com#references) | Yes | References for the consignment |
| customer |  |  | [Customer](https://api-docs.cartoncloud.com#customer) | Yes | Customer for which the consignment is for |
| warehouse |  |  | [Warehouse](https://api-docs.cartoncloud.com#warehouse) |  |  |
| user |  |  | [User](https://api-docs.cartoncloud.com#user) |  | Reference to a driver |
| status |  |  |  |  | *See note below |
| details | collect | address | [Address](https://api-docs.cartoncloud.com#address) | - | Address to collect consignment from (defaults to depot) |
|  | deliver | address | [Address](https://api-docs.cartoncloud.com#address) | - | Address to deliver consignment to (defaults to depot) |
|  |  | requiredDate | Date | - | Date the consignment should be delivered |
|  |  | instructions | String | - | Special delivery instructions |
|  |  | cashPaymentAmount | [Money](https://api-docs.cartoncloud.com#money) | - | Cash on delivery amount to be paid |
|  | invoiceValue |  | [Money](https://api-docs.cartoncloud.com#money) | - | Total invoice value for the consignment. Must be greater than or equal to 0.00 |
|  | manifest |  | [Manifest](https://api-docs.cartoncloud.com#manifest) | - | Reference to a manifest |
|  | type |  |  | - | DELIVERY / DUPLICATE / RETURNED/ PICKUP /POINT_TO_POINT |
|  | authorityToLeave |  | Boolean | - |  |
|  | authorityToLeaveInstructions |  | String | - |  |
|  | deliveryRun |  | [Delivery Run](https://api-docs.cartoncloud.com#delivery-run) | - |  |
|  | runsheet |  | [Run Sheet](https://api-docs.cartoncloud.com#run-sheet) | - |  |
|  | tracking | companyName | String | - | Tracking Company Name |
|  |  | url | String | - | Tracking URL |
| measures | hours |  | Integer | - | Total hours for the consignment |
|  | distance | value | Decimal | - | Total distance for the consignment |
| properties | `{custom}` |  | * | - | Custom fields relating to the consignmentperties |
| items | properties | description | String | - | Free text description of item being transported |
|  |  | `{custom}` | * | - | Custom fields relating to the item |
|  | measures | pallets | Integer | - | Total number of pallets for the item |
|  |  | weight | Decimal | - | Total weight of the item |
|  |  | cubic | Decimal | - | Total cubic of the item |
|  |  | quantity | decimal | - | Quantity of the item |
|  |  | spaces | decimal | - | Total spaces of the item |
|  | details | product | [Product](https://api-docs.cartoncloud.com#product) | - | Product for the item |

| Statuses |
| --- |
| AWAITING_PICKUP |
| AWAITING_POINT_TO_POINT_PICKUP |
| AWAITING_SALE_ORDER_PACKING |
| AWAITING_DROPOFF |
| IN_TRANSIT_PICKUP_WAREHOUSE |
| IN_WAREHOUSE |
| WITH_ON_FORWARDER |
| IN_TRANSIT_WAREHOUSE_DELIVERY |
| IN_TRANSIT_PICK_DELIVERY |
| COLLECTED |
| DELIVERED |
| POINT_TO_POINT_DELIVERED |
| CANCELLED |

#### Response <a id="response"></a>

> Example Response JSON

```json
{
  "id": "028ff38c-a68f-11e8-98d0-529269fb1459",
  "type": "CONSIGNMENT",
  "status": "DRAFT",
  "references": {...},
  "customer": {...},
  "details": {...},
  "measures": {...},
  "properties": {...},
  "items": [...],
  "version": 1
}
```

On success will return status code `201 Created` with the created consignment in the response body. 
The data structure will be the same as in the above request, with the following additional properties.

| JSON Property | Description |
| --- | --- |
| id | UUID for the consignment |
| status | Status of the consignment |
| version | [Version](https://api-docs.cartoncloud.com#entity-version) number for the entity |

### Get Consignment <a id="get-consignment"></a>

Retrieves a previously created consignment

To perform this action, the API Client needs to have the “TMS View Jobs” role.

> **Note**: Any API Client with the **TMS Create Jobs** role automatically has **TMS View Jobs** enabled.

#### Request <a id="request-2"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/consignments/{id}" \
   -H "Accept-Version: 1" \
   -H "Prefer: return=no-items"
```

`GET https://api.cartoncloud.com/tenants/{tenantId}/consignments/{id}`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |
| id | UUID for the consignment |

| Header | Value | Description |
| --- | --- | --- |
| Prefer | return=no-items | If the preference header is applied, items will not be included in the response. |

#### Response <a id="response-2"></a>

> Example Response JSON

```json
{
  "id": "028ff38c-a68f-11e8-98d0-529269fb1459",
  "status": "DRAFT",
  "references": {...},
  "customer": {...},
  "details": {...},
  "items": [...],
  "version": 1
}
```

> Example Response JSON with Prefer Header (return=no-items) provided

```json
{
  "id": "028ff38c-a68f-11e8-98d0-529269fb1459",
  "status": "DRAFT",
  "references": {...},
  "customer": {...},
  "details": {...},
  "version": 1
}
```

On success will return status code `200 OK` with the order in the response body. 
For details on the response data refer to [response for create](https://api-docs.cartoncloud.com#create-consignment)

### Update Consignment <a id="update-consignment"></a>

Updates a previously created Consignment

A Consignment cannot be updated if it is attached to an Invoice that has been Approved

To perform this action, the API Client needs to have the “TMS Create Jobs” role.

#### Request <a id="request-3"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/consignments/{id}" \
   -X PUT \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Content-Type: application/json" \
   -d "{JSON AS BELOW}"
```

`PUT https://api.cartoncloud.com/tenants/{tenantId}/consignments/{id}`

For details on the request data refer to [response for create](https://api-docs.cartoncloud.com#create-consignment)

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |
| id | UUID for the consignment |

| Header | Description |
| --- | --- |
| If-Match | [Version](https://api-docs.cartoncloud.com#entity-version) number for the current entity |

#### Response <a id="response-3"></a>

> Example Response JSON

```json
{
  "id": "028ff38c-a68f-11e8-98d0-529269fb1459",
  "status": "DRAFT",
  "references": {...},
  "customer": {...},
  "details": {...},
  "items": [...],
  "version": 2
}
```

On success will return status code `200 OK` with the updated consignment in the response body.
For details on the response data refer to [response for create](https://api-docs.cartoncloud.com#create-consignment)

Depending on the status of the consignment not all updates will succeed

To cancel a consignment, update the status to

CANCELLED

using the Update Consignment endpoint. A Consignment cannot be cancelled if it is attached to an Invoice that has been Approved.

### Search Consignment <a id="search-consignment"></a>

Search for previously created consignments

To perform this action, the API Client needs to have the “TMS View Jobs” role.

> **Note**: Any API Client with the **TMS Create Jobs** role automatically has **TMS View Jobs** enabled.

#### Request <a id="request-4"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/consignments/search" \
   -X POST \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Content-Type: application/json" \
   -H "Prefer: return=minimal" \
   -d "{JSON AS BELOW}"
```

`POST https://api.cartoncloud.com/tenants/{tenantId}/consignments/search`

> Example Request JSON

```json
{
    "condition": {
        "type": "OrCondition",
        "conditions": [
            {
                "type": "AndCondition",
                "conditions": [
                    {
                        "type": "TextComparisonCondition",
                        "field": {
                            "type": "ValueField",
                            "value": "reference"
                        },
                        "value": {
                            "type": "ValueField",
                            "value": "REF-1"
                        },
                        "method": "STARTS_WITH"
                    },
                    {
                        "type": "TextComparisonCondition",
                        "field": {
                            "type": "ValueField",
                            "value": "customerName"
                        },
                        "value": {
                            "type": "ValueField",
                            "value": "Customer A"
                        },
                        "method": "EQUAL_TO"
                    }
                ]
            }
        ]
    }
}
```

| JSON Property |  | Type | Description |
| --- | --- | --- | --- |
| condition | type | string | Wrap level condition ( OrCondition / AndCondition ) |
|  | conditions | Array of [Search Conditions](https://api-docs.cartoncloud.com#search-condition-types) | All conditions in the array will be combined by the wrap level condition specified in the "type" field |

| Header | Value | Description |
| --- | --- | --- |
| Prefer | return=minimal | Switch the response into minimal representation. If preference applied the Preference-Applied response header will be returned |

Currently these keys are available for search (/conditions/field/value):

| Name | Type | Description |
| --- | --- | --- |
| reference | String | References for the consignment |
| customerName | String | Customer name |
| customerId | String | UUID for the customer |
| runSheetId | String | UUID for the run sheet |
| runSheetDate | String | Run sheet date |
| runSheetName | String | Run sheet name |
| runSheetStatus | String | Run sheet status. Available values - DRAFT / READY_TO_BUILD / BUILDING / BUILT / READY_FOR_DELIVERY |
| driverId | String | UUID for the run sheet driver |
| driverName | String | Run sheet driver name |
| deliveryRunId | String | UUID for the delivery run |
| deliveryRunName | String | Delivery run name |

Currently these keys are available for search (/conditions/field/pointer):

| Pointer | Description |
| --- | --- |
| /generatedFromTask/id | UUID for the Sale order |
| /details/type | Consignment type. Available values - DELIVERY / RETURNED / PICKUP / POINT_TO_POINT / PICKUP_DELIVERY / WAREHOUSE_FULFILMENT |

Condition nesting is possible for complex search. For this purpose the inner condition object can be provided instead of the Search Conditions array (see example)

#### Response <a id="response-4"></a>

> Example Response JSON with Prefer Header provided

```json
[
    {
        "id": "fe84f560-515d-40d8-9760-0c222d7bfde7"
    },
    {
        "id": "4c1c1721-27c8-4bec-a7b7-49c386e0bee7"
    }
]
```

> Example Response JSON without Prefer Header

```json
[
    {
        "id": "fe84f560-515d-40d8-9760-0c222d7bfde7",
        "status": "COLLECTED",
        "references": {
            "customer": "REF-12345"
        },
        "customer": {
            "enabled": true,
            "name": "Customer A",
            "references": {
              "code": "CustomerA"
            },
            "id": "09ecff1f-79f9-4186-9a72-7eedyd1k3f42"
        },
        "details": {...},
        "items": [...],
    },
    {
        "id": "4c1c1721-27c8-4bec-a7b7-49c386e0bee7",
        "status": "COLLECTED",
        "references": {
            "customer": "REF-123"
        },
        "customer": {
            "enabled": true,
            "name": "Customer A",
            "references": {
              "code": "CustomerA"
            },
            "id": "09ecff1f-79f9-4186-9a72-7eedyd1k3f42"
        },
        "details": {...},
        "items": [...],
    }
]
```

On success will return status code 200 with an array of found consignments in response body. The array can be paged (see [Pagination](https://api-docs.cartoncloud.com#pagination))

### Get Quote <a id="get-quote"></a>

Get a Quote for a Consignment

To perform this action, the API Client needs to have the “TMS Create Jobs” role.

#### Request <a id="request-5"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/consignments/quote" \
   -X POST \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Content-Type: application/json" \
   -d "{JSON AS BELOW}"
```

> Example Request JSON

```json
{
  "references": {...},
  "customer": {...},
  "warehouse": {...},
  "taskDate": "2024-08-20",
  "details": {
    "collect": {
      "address": {...},
    },
    "deliver": {
      "address": {...},
      "instructions": "Leave by front door",
      "requiredDate": "2024-08-20",
      "cashPaymentAmount": {...}
    }
    "invoiceValue": {...},
    "manifest": {...},
    "type": {...},
    "authorityToLeave": {...},
    "authorityToLeaveInstructions": {...},
    "deliveryRun": {...},
    "runsheet": {...},
    "tracking": {
      "company": "Tracking company",
      "url": "https://www.example.com/path"
    }
  },
  "properties": {
    "serviceType": "EXPRESS",
    "myCustomField": "info"
  },
  "measures": {
    "hours": 1,
    "distance": {
      "value": 100,
    }
  },
  "items": [
    {
      "properties": {
        "description": "misc equipment"
      },
      "measures": {
        "pallets": 2,
        "weight": 120,
        "quantity": 10
      }
    },
    {
      "measures": {
        "pallets": 3,
        "weight": 160
      },
      "details": {
        "product": {
          "references": {
            "code": "DRUM"
          }
        }
      }
    }
  ]
}
```

`POST https://api.cartoncloud.com/tenants/{tenantId}/consignments/quote`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |

| JSON Property |  |  | Type | Required | Description |
| --- | --- | --- | --- | --- | --- |
| type |  |  | String | - | The type of the order. This defaults to `CONSIGNMENT` when making a request to this endpoint |
| references |  |  | [References](https://api-docs.cartoncloud.com#references) |  | References for the consignment |
| customer |  |  | [Customer](https://api-docs.cartoncloud.com#customer) | Yes | Customer for which the consignment is for |
| warehouse |  |  | [Warehouse](https://api-docs.cartoncloud.com#warehouse) |  | Warehouse for which the consignment is for. If not provided will be assigned to the `default` warehouse. |
| taskDate |  |  | Date |  | Expected date of task to be performed. Used for the rate as well. If not provided will be set to current date. |
| details | collect | address | [Address](https://api-docs.cartoncloud.com#address) | - | Address to collect consignment from (defaults to depot) |
|  | deliver | address | [Address](https://api-docs.cartoncloud.com#address) | - | Address to deliver consignment to (defaults to depot) |
|  |  | requiredDate | Date | - | Date the consignment should be delivered |
|  |  | instructions | String | - | Special delivery instructions |
|  |  | cashPaymentAmount | [Money](https://api-docs.cartoncloud.com#money) | - | Cash on delivery amount to be paid |
|  | invoiceValue |  | [Money](https://api-docs.cartoncloud.com#money) | - | Total invoice value for the consignment. Must be greater than or equal to 0.00 |
|  | type |  |  | - | DELIVERY / DUPLICATE / RETURNED/ PICKUP /POINT_TO_POINT |
|  | authorityToLeave |  | Boolean | - |  |
|  | authorityToLeaveInstructions |  | String | - |  |
|  |  | url | String | - | Tracking URL |
| properties | `{custom}` |  | * | - | Custom fields relating to the consignment |
| measures | hours |  | Integer | - | Total hours for the consignment |
|  | distance | value | Decimal | - | Total distance for the consignment |
| items | properties | description | String | - | Free text description of item being transported |
|  |  | `{custom}` | * | - | Custom fields relating to the item |
|  | measures | pallets | Integer | - | Total number of pallets for the item |
|  |  | weight | Decimal | - | Total weight of the item |
|  |  | cubic | Decimal | - | Total cubic of the item |
|  |  | quantity | decimal | - | Quantity of the item |
|  |  | spaces | decimal | - | Total spaces of the item |
|  | details | product | [Product](https://api-docs.cartoncloud.com#product) | - | Product for the item |

#### Response <a id="response-5"></a>

> Example Response JSON

```json
{
  "rateCard": {
    "name": "Standard Rate Card"
  },
  "rate": {
    "name": "Rate 1"
  },
  "charges": [
    {
      "feeCategory": {
        "id": "7b23a8ab-e186-11e8-8b31-0260b3a835bc",
        "name": "Delivery Fee"
      },
      "description": "2 quantity at $6.00 = $12.00",
      "fee": {
        "amount": 12,
        "currency": "AUD"
      },
      "feeAfterModifiers": {
        "amount": 12,
        "currency": "AUD"
      }
    },
    {
      "description": "Fuel Levy at 5% = $.60 [total: $12.60]",
      "feeCategory": {
        "id": "a43dcec1-7e3a-4f23-9b16-d86fbb31cb1a",
        "name": "Fuel Levy"
      },
      "fee": {
        "amount": 0.6,
        "currency": "AUD"
      },
      "feeAfterModifiers": {
        "amount": 0.6,
        "currency": "AUD"
      }
    },
    {
      "feeCategory": {
        "id": "68c2df33-6fb7-44fa-8a4f-b5439e00a121",
        "name": "Flat Fee"
      },
      "description": "Flat Fee = $10.00",
      "fee": {
        "amount": 10,
        "currency": "AUD"
      },
      "feeAfterModifiers": {
        "amount": 10,
        "currency": "AUD"
      }
    }
  ]
}
```

On success will return status code `200 Success` with a list of charges in the quote response body.

| JSON Property |  |  |  | Description |
| --- | --- | --- | --- | --- |
| rateCard |  |  |  | Rate Card |
|  | name |  |  | Rate Card Name |
| rate |  |  |  | Rate |
|  | name |  |  | Rate Name |
| charges |  |  |  | List of produced charges |
|  | feeCategory |  |  | Fee category |
|  |  | id |  | UUID for the fee category |
|  |  | name |  | Name for the fee category |
|  | description |  |  | A description of the charge |
|  | fee |  |  | The fee for the charge |
|  |  | amount |  | The fee amount |
|  |  | currency |  | The fee currency |
|  | feeAfterModifiers |  |  | The fee after any modifiers have been applied |
|  |  | amount |  | The fee amount |
|  |  | currency |  | The fee currency |

#### Errors <a id="errors"></a>

> Example Error Response JSON

```json
[
    {
      "message": "No matching rate found."
    }
]
```

The endpoint can return errors with status code `422 Unprocessable entity` with a list of error messages. Message content subject to change.

| Message | Description |
| --- | --- |
| No matching rate found. | No rate matching provided criteria. Review from / to zones, service type and effective dates on the rate. |
| Warning, you may be undercharging your customers, please review the charges for this consignment. | Matching rate was found but produced no charges. Review the rate. |
| You may be under-charging this consignment please check all items have been entered correctly. | Matching rate was found but not all items produced a charge. Review the rate. |

## Transport Products <a id="transport-products"></a>

### Create Transport Product <a id="create-transport-product"></a>

Create a new transport product

To perform this action, the API Client needs to have the “TMS Add/Edit Product” role.

#### Request <a id="request"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/products" \
   -X POST \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Content-Type: application/json" \
   -d "{JSON AS BELOW}"
```

`POST https://api.cartoncloud.com/tenants/{tenantId}/products`

> Example Transport Product Request JSON

```json
{
  "scope": "TRANSPORT",
  "references": {
    "code": "FPLT",
    "barcode": "CTNCLD0000000000001"    
  },
  "name": "Frozen Pallet",
  "details": {
    "uiOptions": {
      "consignmentItems": {
        "cubicCalculator": {
          "multiplierField": "PALLETS"
        }
      }
    }
  },
  "properties": {
    "width": 1.2,
    "height": 1.2,
    "length": 1.2,
    "customField": "XYZ"
  }
}
```

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |

| JSON Property |  |  | Type | Required | Description |
| --- | --- | --- | --- | --- | --- |
| type |  |  | String | Yes | `TRANSPORT` for transport product |
| references |  |  | [References](https://api-docs.cartoncloud.com#references) | Yes | References for the product |
| customer |  |  | [Customer](https://api-docs.cartoncloud.com#customer) | - | Customer if product is for a specific customer only |
| name |  |  | String | Yes | Description of the product |
| properties |  |  | `{custom}` | - | Custom properties associated with an entity (length, width, height etc.) |
| details | uiOptions | consignmentItems | cubicCalculator/multiplierField | - | Set to QUANTITY or PALLETS to use that field for cubic multiplier calculation, or NONE to skip cubic calculation. Defaults to QUANTITY when omitted. |
| details | uiOptions | consignmentItems | splitByField | - | Set to QUANTITY or PALLETS to use that field for split grouping, or NONE to disable split grouping. No default value is applied. |
| enabled |  |  | Boolean | - | If the Transport Product is enabled or not (defaults to true) |

#### Response <a id="response"></a>

> Example Response JSON

```json
{
  "id": "318782ea-75b1-11e8-adc0-fa7ae01b9ebc",
  ...
}
```

On success will return status code `201 Created` with the created product in the response body.
The data structure will be the same as in the above request, with the following additional id property.

| JSON Property | Description |
| --- | --- |
| id | UUID for the product |

### List Transport Products <a id="list-transport-products"></a>

Get a list of available transport products

To perform this action, the API Client needs to have at least one of the following roles:

- TMS Create Jobs
- TMS Add/Edit Product

#### Request <a id="request-2"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/products" \
   -X GET \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}"
```

`GET https://api.cartoncloud.com/tenants/{tenantId}/products`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |

#### Response <a id="response-2"></a>

On success will return status code `200 OK` with the list of transport products in the body.

> Example Response JSON

```json
[
  {
    "id": "318782ea-75b1-11e8-adc0-fa7ae01b9ebc",
    "scope": "TRANSPORT",
    "references": {
      "code": "FPLT",
      "barcode": "CTNCLD0000000000001"
    },
    "name": "Frozen Pallet",
    "details": {
      "uiOptions": {
        "consignmentItems": {
          "cubicCalculator": {
            "multiplierField": "PALLETS"
          }
        }
      }
    },
    "properties": {
      "width": 1.2,
      "height": 1.2,
      "length": 1.2,
      "customField": "XYZ"
    }
  },
  ...
]
```

### Get Transport Product <a id="get-transport-product"></a>

To perform this action, the API Client needs to have at least one of the following roles:

- TMS Create Jobs
- TMS Add/Edit Product

#### Request <a id="request-3"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/products/{id}" \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}"
```

`GET https://api.cartoncloud.com/tenants/{tenantId}/products/{id}`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |
| id | UUID for the transport product |

#### Response <a id="response-3"></a>

> Example Response JSON

```json
{
  "id": "318782ea-75b1-11e8-adc0-fa7ae01b9ebc",
  "scope": "TRANSPORT",
  "references": {
    "code": "FPLT"
  },
  "name": "Frozen Pallet",
  "details": {
    "uiOptions": {
      "consignmentItems": {
        "cubicCalculator": {
          "multiplierField": "PALLETS"
        }
      }
    }
  },
  "properties": {
    "width": 1.2,
    "height": 1.2,
    "length": 1.2,
    "customField": "XYZ"
  }
}
```

On success will return status code `200 OK` with the product in the response body.
For details on the response data refer to [response for create](https://api-docs.cartoncloud.com#create-transport-product)

## Documents <a id="documents"></a>

### Create Document <a id="create-document"></a>

Create a new document and attach it to an object in the system (owner).

Note, for API Clients with Customer-Role access, you need to have allowed the Customer to upload documents: [Customer Invoice or Document Upload](https://help.cartoncloud.com/kb2/web-app-page-specific-support/administrator-pages/contacts/customers/edit-customer-or-customer-settings/edit-customer-warehouse-management/customer-sale-order-settings#CustomerSaleOrderSettings-CustomerInvoiceorDocumentUpload)

#### Request <a id="request"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/documents" \
   -X POST \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Content-Type: application/json" \
   -d "{JSON AS BELOW}"
```

> Example Request JSON

```json
{
  "type": "OUTBOUND_ORDER_INVOICE",
  "owner": {
    "type": "OUTBOUND",
    "id": "fb5b56f6-a68e-1168-95d0-52929djs1459"
  },
  "content": {
    "name": "Invoice.pdf",
    "data": "JVBERi0xLjcKJeLjz9MKNSdCAzOCAwIFIKL0...{base64 encoded file content}"
  }
}
```

`POST https://api.cartoncloud.com/tenants/{tenantId}/documents`

| JSON Property |  |  | Type | Required | Description |
| --- | --- | --- | --- | --- | --- |
| type |  |  | String | Yes | Code of document type (*) |
| owner | id |  | String | Yes | Owner object UUID |
|  | type |  | String | Yes | Type of the owner object in the system (ex. OUTBOUND) |
| content | name |  | String | Yes | Name of the uploaded file |
|  | data |  | String | Yes | Base64-encoded content of the file |

(*) Codes of document types with related owner types

| Owner type | Document type | Description |
| --- | --- | --- |
| OUTBOUND | OUTBOUND_ORDER_INVOICE | Outbound invoice |

#### Response <a id="response"></a>

> Example Response JSON

```json
{
  "content": {
    "name": "Invoice.pdf"
  },
  "type": "OUTBOUND_ORDER_INVOICE",
  "owner": {
    "type": "OUTBOUND",
    "id": "2df05c03-8f11-4cba-b78d-7a6f34d34c8b"
  },
  "id": "975487fb-833d-41de-9ac2-114d8e6cb9e2"
}
```

On success will return status code `201 Created` with the created document details in the response body.

## Reports <a id="reports"></a>

Report generation is performed asynchronously. The initial POST to report-runs will start the report generation process and a report-run `id` will be returned (not the report itself). This id can then be used to check if the report has finished generating, and, if so, access the report content. While reports are generating, the `status` of the report-run will be `IN_PROCESS`. Once a report has completed generating the `status` will become `SUCCESS`. If the report generation fails, the status will become `FAILED`.

Depending on the report size and other report-runs requests being processed, reports may take several seconds through to several minutes in order to complete generation. After the initial POST request, we recommend sending the first GET request 10 seconds later, and if still `IN_PROCESS`, using exponential back-off polling (20s delay, 40s delay, 80s delay etc).

### Create report run <a id="create-report-run"></a>

Create a report run

Each report run object consists of 2 fields

| JSON Property |  |  | Type | Required | Description |
| --- | --- | --- | --- | --- | --- |
| type |  |  | String | Yes | Report type |
| parameters |  |  | Object | Yes | Parameters specific for report type |

Once you have run the report, you will receive the returned JSON object. The returned JSON object may differ from what you provided in the request. For example, the pageSize may reduce to match the allowed maximum. In addition, default parameters may be added if they were not provided in the request. The status will read as; IN_PROCESS.

Most report processing will not take longer than several seconds; however, if the status is still IN_PROCESS after one minute of creation, we recommend sending the request again.

To access the report results, you will need to use the id provided. You will use this id for calling the Get endpoint to receive the report results.

### Stock on hand report <a id="stock-on-hand-report"></a>

To perform this action, the API Client needs to have the “WMS Create Job” role.

#### Request <a id="request"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/report-runs" \
   -X POST \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Content-Type: application/json" \
   -d "{JSON AS BELOW}"
```

`POST https://api.cartoncloud.com/tenants/{tenantId}/report-runs`

> Example Stock on hand report run Request JSON

```json
{
  "type": "STOCK_ON_HAND",
  "parameters": {
    "pageSize": 100,
    "warehouse": {
      "name": "Default"
    },
    "customer": {
      "id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6"
    },
    "aggregateBy": [
      "productType",
      "inboundOrder"
    ]
  }
}
```

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |

| JSON Property |  |  | Type | Required | Description |
| --- | --- | --- | --- | --- | --- |
| type |  |  | String | Yes | STOCK_ON_HAND |
| parameters |  |  | Object | Yes |  |
|  | pageSize |  | Integer | - | Number of items per page. If not provided default value will be applied. Maximum value for Stock on hand report is 100 |
|  | warehouse |  | [Warehouse](https://api-docs.cartoncloud.com#warehouse) | - | Warehouse reference. If not provided will be set to the `default` warehouse |
|  | customer |  | [Customer](https://api-docs.cartoncloud.com#customer) | Yes | Customer which stock will be analyzed |
|  | aggregateBy |  | array | - | Criteria used to aggregate stock. NB, some criteria will always be applied. Please see aggregateBy criteria table below |

#### Available aggregateBy criteria list: <a id="available-aggregateby-criteria-list"></a>

| Name | Always applied | Description | Limitation |
| --- | --- | --- | --- |
| productType |  | Product type |  |
| productGroup |  | Product group |  |
| productStatus | Yes | Product status |  |
| unitOfMeasure | Yes | Product unit of measure |  |
| inboundOrder |  | Inbound order reference |  |
| location |  | Warehouse location | Available only for api clients with unlimited customers access |

NB. Additional to these criteria you can provide the customer's product custom fields or purchase order product custom fields, eg. expiryDate, batch, barcode

#### Response <a id="response"></a>

> Example Stock on hand report run Response JSON

```json
{
 "type": "STOCK_ON_HAND",
 "status": "IN_PROCESS",
 "parameters": {
  "pageSize": 100,
  "warehouse": {
   "name": "Default"
  },
  "customer": {
   "id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6"
  },
  "aggregateBy": [
   "productType",
   "inboundOrder",
   "unitOfMeasure",
   "productStatus"
  ]
 },
 "id": "8d0ada6a-9414-4cfe-83b6-ac09689373cd"
}
```

On success will return status code `201 Created` with the created report run object in the response body.

### Bulk charges report <a id="bulk-charges-report"></a>

To perform this action, the API Client needs to have the “Internal Field Access” role.

#### Request <a id="request-2"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/report-runs" \
   -X POST \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}" \
   -H "Content-Type: application/json" \
   -d "{JSON AS BELOW}"
```

`POST https://api.cartoncloud.com/tenants/{tenantId}/report-runs`

> Example Bulk charges report run Request JSON

```json
{
  "type": "BULK_CHARGES",
  "parameters": {
    "pageSize": 100,
    "dateFilter": "date_added",
    "fromDate": "2023-10-01",
    "toDate": "2023-10-07",
    "customers": [
      {
        "id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6"
      }
    ],
    "chargeClasses":[
      "CONSIGNMENT",
      "MANIFEST",
      "SALE_ORDER",
      "PURCHASE_ORDER",
      "STORAGE_PERIOD",
      "RUN_SHEET"
    ]
  }
}
```

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |

| JSON Property |  | Type | Required | Description |
| --- | --- | --- | --- | --- |
| type |  | String | Yes | BULK_CHARGES |
| parameters |  | Object | Yes |  |
|  | pageSize | Integer | - | Specify the number of items per page. If not provided, the default value will be applied. The maximum value for Bulk charges report is 100. |
|  | dateFilter | String | - | Filter the results by date. |
|  | fromDate | Date | - | Specify the start range of entity created date or invoice date. YYYY-MM-DD formatted. |
|  | toDate | Date | - | Specify the end range of entity created date or invoice date. YYYY-MM-DD formatted. |
|  | customers | array[Customer](https://api-docs.cartoncloud.com#customer) | - | Filter the results by customers which Charges belongs to. |
|  | chargeClasses | array | - | Filter the results by Charge class. Please see chargeClasses criteria table below. |

#### Available chargeClasses criteria list: <a id="available-chargeclasses-criteria-list"></a>

| Name | Description |
| --- | --- |
| CONSIGNMENT | Charges for Consignments |
| MANIFEST | Charges for Manifests |
| SALE_ORDER | Charges for Sale Orders |
| PURCHASE_ORDER | Charges for Purchase Orders |
| STORAGE_PERIOD | Charges for Storage Periods |
| RUN_SHEET | Charges for Run Sheets |

#### Activity Date definitions for each entity type / charge class: <a id="activity-date-definitions-for-each-entity-type-charge-class"></a>

| Name | Description |
| --- | --- |
| CONSIGNMENT | Date Delivered for Consignments |
| MANIFEST | Date Added for Manifests |
| SALE_ORDER | Date Packed for SOs |
| PURCHASE_ORDER | Date Allocated for POs |
| STORAGE_PERIOD | Work off Storage Periods start/end date. |
| RUN_SHEET | Delivery date for RunSheets |

#### Response <a id="response-2"></a>

> Example Bulk charges report run Response JSON

```json
{
  "type": "BULK_CHARGES",
  "status": "IN_PROCESS",
  "parameters": {
    "pageSize": 100,
    "dateFilter": "date_added",
    "fromDate": "2023-10-01",
    "toDate": "2023-10-07",
    "customers": [
      {
        "id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6"
      }
    ],
    "chargeClasses":[
      "CONSIGNMENT",
      "MANIFEST",
      "SALE_ORDER",
      "PURCHASE_ORDER",
      "STORAGE_PERIOD",
      "RUN_SHEET"
    ]
  },
  "id": "8d0ada6a-9414-4cfe-83b6-ac09689373cd"
}
```

On success will return status code `201 Created` with the created report run object in the response body.

| JSON Property | Type | Description |
| --- | --- | --- |
| id | string | UUID for the report run |
| status | string | IN_PROCESS / SUCCESS / FAILED |

### Get Report Run results <a id="get-report-run-results"></a>

Retrieve the report run results.

If the response is successful, the return status code will be 200 OK with the report run object and report items. The pagination header is provided to iterate through the pages (see [Pagination](https://api-docs.cartoncloud.com#pagination)).

If the report fails, the GET request will still return the status code 200 OK with the report run object, however, it will also show the error details.

Each report run data is stored for 7 days from the time of processing. After this period of time the request will return a 404 Not Found Response.

#### Request <a id="request-3"></a>

> Example Request

```bash
curl "https://api.cartoncloud.com/tenants/{tenantId}/report-runs/{id}" \
   -H "Accept-Version: 1" \
   -H "Authorization: Bearer {accessToken}"
```

`GET https://api.cartoncloud.com/tenants/{tenantId}/report-runs/{id}`

| URL Property | Description |
| --- | --- |
| tenantId | UUID for the [tenant](https://api-docs.cartoncloud.com#tenant) |
| id | UUID for the report run |

#### Response of Stock on hand report (SUCCESS) <a id="response-of-stock-on-hand-report-success"></a>

> Example SUCCESS Response JSON of Stock on hand report

```json
{
    "type": "STOCK_ON_HAND",
    "status": "SUCCESS",
    "reportTime": "2021-07-16 14:15:16",
    "parameters": {
        "pageSize": 100,
        "warehouse": {
            "name": "Default"
        },
        "customer": {
            "id": "791a3061-383d-4759-a3b4-0bc89d48608d"
        },
        "aggregateBy": [
            "productType",
            "inboundOrder",
            "unitOfMeasure",
            "productStatus"
        ]
    },
    "items": [
        {
            "details": {
                "product": {
                    "customer": {...},
                        "id": "791a3061-383d-4759-a3b4-0bc89d48608d"
                    },
                    "name": "Dark Chocolate Cookies",
                    "references": {
                        "code": "COOKIES123"
                    },
                    "id": "089c89d4-0080-4fe9-855b-8ccf29d5ebf8"
                },
                "unitOfMeasure": {
                    "type": "UNIT",
                    "name": "UNIT"
                }
            },
            "type": "ITEM",
            "measures": {
                "quantity": 7140,
                "quantityFree": 7100,
                "quantityIncoming": 0,
                "quantityAllocated": 40
            },
            "properties": {
                "productType": "General",
                "inboundOrder": {
                    "id": "b51c26f7-59d9-49cc-924f-d47a481d3468"
                },
                "unitOfMeasure": {
                    "type": "UNIT",
                    "name": "UNIT"
                },
                "location": {
                    "name": "LL-6-2",
                    "id": "791d28d1-250a-4b55-9f64-0977244a36bd"
                },
                "productStatus": "OK"
            }
        },
        {...},
        {...}
    ],
    "id": "8d0ada6a-9414-4cfe-83b6-ac09689373cd"
}
```

| JSON Property |  |  | Type | Description |
| --- | --- | --- | --- | --- |
| id |  |  | string | UUID for the report run |
| status |  |  | string | SUCCESS |
| reportTime |  |  | DateTime | Time of the report |
| items | details | product | [Product](https://api-docs.cartoncloud.com#product) | Product reference |
|  | unitOfMeasure | [UnitOfMeasure](https://api-docs.cartoncloud.com#unitofmeasure) | The unit of measure for the product. |  |
| measures | quantity | Decimal | The amount of stock in the Warehouse |  |
|  | quantityFree | Decimal | The amount of stock that has not been allocated to Sale Orders |  |
|  | quantityAllocated | Decimal | The amount of stock that has been allocated to Sale Orders |  |
|  | quantityIncoming | Decimal | The amount of stock on Purchase Orders with status of "Not Yet Received" |  |
| properties | `{custom}` | * | Product properties unique for provided aggregatedBy values. All provided aggregatedBy values will be returned as properties of the report item |  |

#### Response of Bulk charges report (SUCCESS) <a id="response-of-bulk-charges-report-success"></a>

> Example SUCCESS Response JSON of Bulk charges report

```json
{
    "type": "BULK_CHARGES",
    "status": "SUCCESS",
    "reportTime": "2021-07-16 14:15:16",
    "parameters": {
        "pageSize": 100,
        "dateFilter": "date_added",
        "fromDate": "2023-10-01",
        "toDate": "2023-10-07",
        "customers": [
          {
            "id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6"
          }
        ],
        "chargeClasses":[
          "CONSIGNMENT",
          "MANIFEST",
          "SALE_ORDER",
          "PURCHASE_ORDER",
          "STORAGE_PERIOD",
          "RUN_SHEET"
        ]
    },
    "items": [
      {
        "id": "45046",
        "uuid": "ace2dd01-0491-4666-ba9b-ea7b4f214bf1",
        "createdDate": "2023-05-03 16:43:21",
        "activityDate": "2023-05-04 16:43:21",
        "customer": "Customer name",
        "parentEntity": "Consignment",
        "parentReference": "Consignment Ref",
        "parentId": "259",
        "parentUuid": "851e8059-5611-4827-9b5d-a14027f76a13",
        "invoiceId": "844",
        "invoiceStartDate": "2023-05-01",
        "invoiceEndDate": "2023-05-07",
        "type": "Income",
        "automatic": "Yes",
        "feeCategory": "Delivery",
        "account": "Freight Income",
        "description": "Flat Fee = $600.00",
        "qty": 0,
        "charge": 600,
        "warehouseName": "Test Warehouse"
      }
    ],
    "id": "8d0ada6a-9414-4cfe-83b6-ac09689373cd"
}
```

| JSON Property |  | Type | Description |
| --- | --- | --- | --- |
| id |  | string | UUID for the report run. |
| status |  | string | SUCCESS. |
| reportTime |  | DateTime | Time of the report. |
| items | id | String | ID of Charge. |
|  | uuid | String | UUID of Charge. |
|  | createdDate | String | Charges entity created date. |
|  | activityDate | String | Charges entity activity date. (Only shown when the date filter is set to date_activity) |
|  | customer | String | Customer name. |
|  | parentEntity | String | Charge class. |
|  | parentReference | String | Reference of Charge entity. |
|  | parentId | String | ID of Charge entity. |
|  | parentUuid | String | UUID of Charge entity. |
|  | invoiceId | String | ID of Invoice which Charge is attached to. |
|  | invoiceStartDate | String | Start date of Invoice. |
|  | invoiceEndDate | String | End date of Invoice. |
|  | type | String | Income/Expense. |
|  | automatic | String | Whether Charge is automatically created. |
|  | feeCategory | String | Fee category. |
|  | account | String | Account. |
|  | description | String | Charge description. |
|  | qty | Float | Charge Quantity. |
|  | charge | Float | Charge amount. |
|  | warehouseName | String | Warehouse name. |

#### Response (FAILURE) <a id="response-failure"></a>

> Example FAILED Response JSON

```json
{
    "type": "STOCK_ON_HAND",
    "status": "FAILED",
    "reportTime": "2021-07-20 06:04:33",
    "parameters": {
        "pageSize": 100,
        "warehouse": {
            "name": "Default"
        },
        "customer": {
            "id": "791a3061-383d-4759-a3b4-0bc89d48608d"
        },
        "aggregateBy": [
            "productType",
            "inboundOrder",
            "unitOfMeasure",
            "productStatus"
        ]
    },
    "failureDetails": [
        {
            "field": "/parameters",
            "message": "Cannot configure report using provided parameters"
        }
    ],
    "id": "61020e13-e53b-45f7-906c-e401a83d880e"
}
```

| JSON Property |  | Type | Description |
| --- | --- | --- | --- |
| id |  | string | UUID for the report run |
| status |  | string | FAILED |
| reportTime |  | DateTime | Time of the report |
| failureDetails |  | Object | Errors occurred |

## Standard Elements <a id="standard-elements"></a>

### References <a id="references"></a>

```json
{
  "customer": "REF-1234",
  "tracking": "123-456-EXT",
  "alternateReference": "ALT-REF-5678"
}
```

References are a set of external or alternate references for the resource. 
These may or may not be unique depending on the specific configuration for the tenant and customer. 
The primary reference or identifier for resources will always be the `id` which is a UUID

| Property | Description |
| --- | --- |
| customer | Customer supplied reference |
| tracking | External tracking number used in consignments |
| {reference type} | Other custom references maybe defined for the tenant |

### Customer <a id="customer"></a>

```json
{
  "id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
  "name": "Customer A",
  "references": {
    "code": "C123456"
  }
}
```

A customer can be referenced using any one of the properties below. 
Where multiple properties are supplied the first property as listed below will be used.

| Property |  | Description |
| --- | --- | --- |
| id |  | UUID for the customer |
| references | code | Customer code |
| name |  | Name of the customer |

### Warehouse <a id="warehouse"></a>

```json
{
  "id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
  "name": "Example Warehouse"
}
```

A warehouse can be referenced using any one of the properties below. 
Where multiple properties are supplied the first property as listed below will be used.

| Property | Description |
| --- | --- |
| id | UUID for the warehouse |
| name | Name of Warehouse (exactly as spelt in CartonCloud) |

### Address <a id="address"></a>

```json
{
  "companyName": "Company A",
  "contactName": "Mr Smith",
  "address1": "1 Main Street",
  "address2": "Unit 2, Corporate Tower",
  "suburb": "Springfield",
  "city": "Metropolis",
  "state": {...},
  "postcode": "4000",
  "country": {...},
  "phone": "07 5512 3456",
  "email": "info@company.com"
}
```

| Property | Type | Required | Description |
| --- | --- | --- | --- |
| companyName | string | companyName or contactName | Name of the company |
| contactName | string | companyName or contactName | Contact person's name |
| address1 | string | for a complete address | First line of street address |
| address2 | string | No | Additional address information (e.g. unit, apartment, suite) |
| suburb | string | No | Suburb |
| city | string | for a complete address | City |
| state | [State](https://api-docs.cartoncloud.com#state) | No | State, region or prefecture information |
| postcode | string | No | Post code (zip code) |
| country | [Country](https://api-docs.cartoncloud.com#country) | for a complete address | Country information |
| phone | string | No | Phone number. Valid phone number must be a string between 0 to 64 characters. |
| email | string | No | Email address. Valid emails must not start with a full stop (a period), must not start with or contain any spaces, and must have data before and after an @ symbol. |

### State <a id="state"></a>

```json
{
  "code": "QLD",
  "name": "Queensland"
}
```

A state can be referenced using any one of the properties below. 
Where multiple properties are supplied the first property as listed below will be used.

| Property | Description |
| --- | --- |
| code | The code used to denote the state |
| name | The name of the state |

### Country <a id="country"></a>

```json
{
  "name": "Australia",
  "iso2Code": "AU",
  "iso3Code": "AUS"
}
```

A country can be identified using any of the properties listed in the table below.

If multiple properties are provided, the system checks them in the order shown in the table — from top to bottom.
The lookup will succeed only if the first provided property in that order corresponds to a valid country.

If the first provided property (for example, iso2Code) does not correspond to a valid country, the system will not evaluate the remaining properties.

| Property | Description |
| --- | --- |
| iso2Code | The ([ISO Alpha-2 Code](https://www.iso.org/obp/ui/#search)) Code of the country |
| iso3Code | The ([ISO Alpha-3 Code](https://www.iso.org/obp/ui/#search)) Code of the country |
| name | The name of the country |

### DeliveryMethod <a id="deliverymethod"></a>

The type of method used to transfer order items to a customer.

```json
{
  "type": "SHIPPING",
  "requestedService": "Standard"
}
```

| Property | Description | Type | Default |
| --- | --- | --- | --- |
| type | The type of delivery method | Enum | `SHIPPING` |
|  |  | - `SHIPPING` A delivery to a customer using a shipping carrier |  |
|  |  | - `PICKUP` A delivery that a customer picks up from your warehouse, or other location that you choose |  |
| requestedService | Requested shipping service. For example 'Standard', 'Express', 'Overnight' etc. | String |  |

### Product <a id="product"></a>

```json
{
  "id": "c3706e8c-7526-11e8-adc0-fa7ae01b3ebc",
  "name": "Product Name",
  "references": {
      "code": "SKU123",
      "barcode": "00123246586"
  }
}
```

A product can be referenced using any one of the properties below. 
Where multiple properties are supplied the first property as listed below will be used.

| Property |  | Description |
| --- | --- | --- |
| id |  | UUID for the product |
| references | code | Product code |
|  | barcode | Product barcode |
| name |  | Name of the Product |

### UnitOfMeasure <a id="unitofmeasure"></a>

```json
{
  "type": "CARTON"
}
```

A unit of measure can be referenced using the property below.

| Property | Description |
| --- | --- |
| type | The code of the unit of measure being used |

### Money <a id="money"></a>

```json
{
  "amount": 1000,
  "currency": "AUD"
}
```

The provided currency must be a valid [ISO 4217 Currency Code](https://www.iso.org/iso-4217-currency-codes.html) and must match the tenant default currency unless otherwise specified by the field's documentation.

| Property | Type | Description |
| --- | --- | --- |
| amount | Decimal | The amount being used for the field |
| currency | string | The currency being used for the field |

### Delivery Run <a id="delivery-run"></a>

```json
{
    "id": "7b34abb4-e186-11e8-8b31-0260123835bc",
    "name": "Delivery Run Name",
    "warehouse": {
        "enabled": true,
        "name": "Default",
        "id": "93d12a9a-cb7d-1as8-8b31-026943a835bc"
    }
}
```

| Property | Type | Description |
| --- | --- | --- |
| id | string | UUID for the delivery run |
| name | string |  |
| warehouse | [Warehouse](https://api-docs.cartoncloud.com#warehouse) |  |

### Run Sheet <a id="run-sheet"></a>

```json
{
  "id": "93d12a9a-cb7d-1as8-8b31-026943a835bc",
  "name": "Run Sheet Name",
  "date":  "2020-08-04"
}
```

| Property | Type | Description |
| --- | --- | --- |
| id | string | UUID for the run sheet |
| name | string |  |
| date | Date |  |

### Manifest <a id="manifest"></a>

```json
{
  "id": "c3706e8c-7526-11e8-adc0-fa7ae01b3ebc"
}
```

| Property | Type | Description |
| --- | --- | --- |
| id | string | UUID for the product |

### User <a id="user"></a>

```json
{
  "id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
  "name": "John Smith"
}
```

| Property | Description |
| --- | --- |
| id | UUID for the user |
| name | Name of the user |

### Search Condition Types <a id="search-condition-types"></a>

There are several condition types supported - Text, Boolean, Numeric, Date, DateTime

#### Text <a id="text"></a>

```json
{
    "type": "TextComparisonCondition",
    "field": {
        "type": "JsonField",
        "pointer": "/references/customer"
    },
    "value": {
        "type": "ValueField",
        "value": "REF-1234"
    },
    "method": "EQUAL_TO"
}

{
    ...
    "field": {
        "type": "ValueField",
        "value": "reference"
    },
    ...
}
```

| Property | Type | Description |
| --- | --- | --- |
| type | string | TextComparisonCondition |
| field | [Search Condition Json Field](https://api-docs.cartoncloud.com#search-condition-json-field) / [Search Condition Value Field](https://api-docs.cartoncloud.com#search-condition-value-field) | Object explaining field to match |
| value | [Search Condition Value Field](https://api-docs.cartoncloud.com#search-condition-value-field) | Object explaining searchable value |
| method | string | Method used for searching (EQUAL_TO / NOT_EQUAL_TO / CONTAINS / DOES_NOT_CONTAIN / STARTS_WITH) |

#### Boolean <a id="boolean"></a>

```json
{
    "type": "BooleanComparisonCondition",
    "field": {
        "type": "JsonField",
        "pointer": "/enabled"
    },
    "value": {
        "type": "ValueField",
        "value": true
    }
}
```

| Property | Type | Description |
| --- | --- | --- |
| type | string | BooleanComparisonCondition |
| field | [Search Condition Json Field](https://api-docs.cartoncloud.com#search-condition-json-field) / [Search Condition Value Field](https://api-docs.cartoncloud.com#search-condition-value-field) | Object explaining field to match |
| value | [Search Condition Value Field](https://api-docs.cartoncloud.com#search-condition-value-field) | Object explaining searchable value |

#### Numeric <a id="numeric"></a>

```json
{
    "type": "NumericComparisonCondition",
    "field": {
        "type": "JsonField",
        "pointer": "/references/numericId"
    },
    "value": {
        "type": "ValueField",
        "value": 123
    },
    "method": "LESS_THAN"
}
```

| Property | Type | Description |
| --- | --- | --- |
| type | string | NumericComparisonCondition |
| field | [Search Condition Json Field](https://api-docs.cartoncloud.com#search-condition-json-field) / [Search Condition Value Field](https://api-docs.cartoncloud.com#search-condition-value-field) | Object explaining field to match |
| value | [Search Condition Value Field](https://api-docs.cartoncloud.com#search-condition-value-field) | Object explaining searchable value |
| method | string | Method used for searching (EQUAL_TO / NOT_EQUAL_TO / GREATER_THAN / GREATER_THAN_OR_EQUAL_TO / LESS_THAN / LESS_THAN_OR_EQUAL_TO) |

#### Date <a id="date"></a>

```json
{
    "type": "DateComparisonCondition",
    "field": {
        "type": "JsonField",
        "pointer": "/details/collect/requiredDate"
    },
    "value": {
        "type": "ValueField",
        "value": "2022-01-15"
    },
    "method": "GREATER_THAN"
}
```

| Property | Type | Description |
| --- | --- | --- |
| type | string | DateComparisonCondition |
| field | [Search Condition Json Field](https://api-docs.cartoncloud.com#search-condition-json-field) / [Search Condition Value Field](https://api-docs.cartoncloud.com#search-condition-value-field) | Object explaining field to match |
| value | [Search Condition Value Field](https://api-docs.cartoncloud.com#search-condition-value-field) | Object explaining searchable value |
| method | string | Method used for searching (EQUAL_TO / NOT_EQUAL_TO / GREATER_THAN / GREATER_THAN_OR_EQUAL_TO / LESS_THAN / LESS_THAN_OR_EQUAL_TO) |

#### DateTime <a id="datetime"></a>

```json
{
    "type": "DateTimeComparisonCondition",
    "field": {
        "type": "JsonField",
        "pointer": "/timestamps/dispatched/time"
    },
    "value": {
        "type": "ValueField",
        "value": "2025-01-12:00:00+10:00"
    },
    "method": "GREATER_THAN"
}
```

| Property | Type | Description |
| --- | --- | --- |
| type | string | DateTimeComparisonCondition |
| field | [Search Condition Json Field](https://api-docs.cartoncloud.com#search-condition-json-field) / [Search Condition Value Field](https://api-docs.cartoncloud.com#search-condition-value-field) | Object explaining field to match |
| value | [Search Condition Value Field](https://api-docs.cartoncloud.com#search-condition-value-field) | Object explaining searchable value |
| method | string | Method used for searching (EQUAL_TO / NOT_EQUAL_TO / GREATER_THAN / GREATER_THAN_OR_EQUAL_TO / LESS_THAN / LESS_THAN_OR_EQUAL_TO) |

### Search Condition Json Field <a id="search-condition-json-field"></a>

**Recommended**: When both JsonField and ValueField options are available for the field parameter, use JsonField instead of ValueField (deprecated).

```json
{
    "type": "JsonField",
    "pointer": "/references/customer"
}
```

| Property | Type | Description |
| --- | --- | --- |
| type | string | 'JsonField' |
| pointer | string | JSON pointer path |

### Search Condition Value Field (deprecated) <a id="search-condition-value-field-deprecated"></a>

```json
{
    "type": "ValueField",
    "value": "reference"
}
```

| Property | Type | Description |
| --- | --- | --- |
| type | string | 'ValueField' |
| value | string / boolean / decimal |  |

### Timestamp <a id="timestamp"></a>

```json
{
    "time": "2025-05-30T14:14:16+10:00"
}
```

| Property | Type | Description |
| --- | --- | --- |
| time | string | ISO 8601 formatted timestamp |

### Error Reference <a id="error-reference"></a>

```json
{
    "message": "Ice Cream (IC-123) x 2 CTN - Product not found",
    "isResolved": false
}
```

| Property | Type | Description |
| --- | --- | --- |
| message | string | Error details |
| isResolved | boolean | Current status of the error |

### Custom Fields <a id="custom-fields"></a>

Custom Fields may exist or may be requested by the tenant.

- If needing to use Custom Fields in these entities Address, Shipment, Container, Consignment Data, Consignment Item, Vehicle, Customer, Driver, Sale Order, Purchase Order or Transport Product, use the name in the 'Mapped Field' which can be obtained from the tenant.
- For the Sale Order Product - SOP Custom Fields, use the relevant custom field name e.g. sop_custom_field_1, sop_custom_field_2, etc.
- For other entities such as Purchase Order Product POP Custom Field and for Product, use the relevant generic custom field name e.g. custom_field_1, custom_field_2, etc.

## Webhooks <a id="webhooks"></a>

Webhooks are available for most entity changes, and can be configured based on conditions (ie: specific customer, specific status etc).

### Configuring Webhooks <a id="configuring-webhooks"></a>

At this time, webhooks need to be setup by CartonClouds Integration staff.

To request a webhook to be configured, please contact [integrations@cartoncloud.com.au](mailto:integrations@cartoncloud.com.au?subject=Webhook%20Request)

## Responses <a id="responses"></a>

### Success Status Codes <a id="success-status-codes"></a>

The following HTTP status codes are used for successful requests.

| Status Code | Description | Reason |
| --- | --- | --- |
| 200 | Success | Successfully completed request |
| 201 | Created | The entity was successfully created |
| 228 | Created with issues | The entity was created, but has issues that may need to be addressed |

### Error Status Codes <a id="error-status-codes"></a>

If there are any errors with the request, an error status code will be returned along 
with further details of the error in the response body as an array of JSON error objects.

| Status Code | Description | Reason |
| --- | --- | --- |
| 400 | Bad Request | Request is invalid |
| 401 | Unauthorized | Access token or credentials are not valid |
| 403 | Forbidden | No permissions to access the resource |
| 404 | Not Found | The resource does not exist, is an invalid URL or unknown version |
| 405 | Method Not Allowed | Invalid method (GET, POST, PUT, etc.) |
| 406 | Not Acceptable | Invalid Accept-Version header provided |
| 409 | Conflict | Operation cannot be performed as the resource has been modified by another request |
| 412 | Precondition Failed | Server does not meet one of the preconditions provided in the request header fields |
| 422 | Unprocessable Entity | Structure of the request is valid, but data content is invalid or not compatible with the request |
| 429 | Too Many Requests | Rate limiting has been applied |
| 500 | Internal Server Error | An issue with our server. Try again later. |
| 503 | Service Unavailable | Temporarily offline for maintenance. Try again later. |

### Error Response Data <a id="error-response-data"></a>

#### General <a id="general"></a>

> Example Response JSON

```json
[
  {
    "message": "Request method 'PUT' not supported"
  }
]
```

Some errors will simply return a text description of the error encountered, but will still follow the same data structure.

| Property | Description |
| --- | --- |
| message | A description of the error |

Error codes issued in payload responses:

| Code | Description |
| --- | --- |
| 10100 | Consignment not found |
| 10200 | Multiple consignments found |
| 10201 | Consignment is group child |
| 10202 | Consignment not approved |
| 10203 | Unable to allocate consignment |
| 10204 | Consignment not allocated to run |
| 10205 | Unable to update to In Warehouse |
| 10206 | Driver not found |
| 10207 | Consignment not allocated to Run and no Run given |
| 10208 | Delivery Run not found |
| 10209 | Unable to create Run Sheet |
| 10210 | Run Sheet not found |
| 10211 | Invalid request |
| 10212 | Consignment already allocated |
| 10213 | Cannot allocate Consignment |
| 10214 | Consignment already In Warehouse |
| 10300 | Storage Period cannot be created |
| 10301 | Storage Period duplicate |
| 10400 | Sale Order not found |
| 10401 | Sale Order not Packing In Progress |
| 10402 | Sale Order Rejected |
| 10403 | Sale Order import error duplicate |
| 10404 | Sale Order import error wrong Warehouse |
| 10405 | Sale Order import error unauthorized Warehouse |
| 10406 | Sale Order import error Customer does not exist |
| 10443 | Product error |
| 10444 | Product error expired |
| 10445 | Product error expiry threshold |
| 10446 | Product error warning threshold |
| 10447 | Product error out of stock |
| 10448 | Product error not enough stock |
| 10449 | Product error Product not found |
| 10450 | Product error Product deactivated |
| 10451 | Product error Product qty is not number |
| 10452 | Product error Product qty is negative |
| 10453 | Product error Product qty is zero |
| 10454 | Product error Product conversion failed |
| 10455 | Product error invalid Unit Of Measure |
| 10456 | Product error unable to parse |
| 10457 | Product error too many products found |
| 10458 | Product error qty not whole |
| 10459 | Product error product code not specified |
| 11000 | Customer not found |
| 12000 | Purchase Order potentially undercharged storage |

#### Validation <a id="validation"></a>

A request data validation error will return the error code 422 and the following response

> Example Response JSON

```json
[
  {
    "field": "/name",
    "message": "Name cannot be empty."
  },
  {
    "field": "/description",
    "message": "Description cannot be empty."
  }
]
```

```json
[
  {
    "field": "/references/customer",
    "message": "A Purchase Order with this Customer Reference already exists.",
    "type": "DUPLICATE",
    "details": {
      "duplicateId": "cd639009-1111-4a89-bf83-8907b8c9d09a"
    }
  }
]
```

An array of validation errors with the fields for which the error applies will be returned.

| Property | Description |
| --- | --- |
| field | The property field for which the error applies as a [JSON Pointer](https://tools.ietf.org/html/rfc6901) |
| message | A description of the validation error |
| type (optional) | The specific type of error |
| details (optional) | An array containing errors with extra info |

#### Validation Error Type <a id="validation-error-type"></a>

| Type | Properties of Details | Description |
| --- | --- | --- |
| DUPLICATE | duplicateId | The id of duplicate existing record |
