# Validation Service API Documentation

## Overview

The Validation Service is a microservice that handles inventory and computer vision validations and management for the coffee shop system. It communicates via RabbitMQ message queues and provides these main functions:

**For inventory:**

- **Pre-check**: Validate ingredient availability before order/item processing.
- **Update Inventory**: Update ingredient levels after consumption.
- **Ingredient Status**: Get the current ingredients' status and levels.
- **Refill Inventory:** Refill the inventory **(TO-DO: refill function and rules).**

**For Computer Vision:**

- **Check cup picked:**
- **Check cup placed:**
- **Check coffee beans:**

**Note:** This documentation focuses only on the inventory since CV has not yet been implemented.

## Connection Details

### RabbitMQ Configuration

- **Input Queue**: validation_queue
- **Output Queues**:
  - scheduler_response_queue (for scheduler service)
  - dashboard_response_queue (for dashboard service)
- **Message Format**: JSON
- **Persistence**: All messages are durable (which means they don't get lost if the connection stops or an error happens).

## Request Format

All requests must follow this structure:

```json
{
  "request_id": "unique-identifier",
  "client_type": "scheduler/dashboard",
  "function_name": "pre_check/update_inventory/ingredient_status",
  "payload": {
    // Function-specific data
  }
}
```

### Required Fields

- **request_id**: Unique identifier for tracking the request,
  - note: can be generated randomly: str(uuid.uuid4())
- **client_type**: Must be either "scheduler" or "dashboard"
- **function_name**: The operation to perform
- **payload**: Function-specific request data

## Function 1: Pre-Check (pre_check)

**Purpose**: Validate if ingredients are available for order processing

**Client**: Scheduler Service

### Request Structure

```json
{
  "request_id": "275ceafa-59e7-4639-b35f-61234f2ec634",
  "client_type": "scheduler",
  "function_name": "pre_check",
  "payload": {
    "items": [
      {
        "drink_name": "cappuccino",
        "size": "small",
        "cup_id": "H9",
        "temperature": "hot",
        "ingredients": {
          "espresso": {
            "type": "regular",
            "amount": 1
          },
          "milk": {
            "type": "whole",
            "amount": 150
          }
        }
      }
    ]
  }
}
```

### Response Structure

```json
{
  "passed": false,
  "details": {
    "cappuccino": {
      "status": false,
      "cup": {
        "type": "H9",
        "current": 19.0,
        "needed": 1,
        "critical_threshold": 25,
        "status": false
      },
      "espresso": {
        "type": "regular",
        "current": 17.0,
        "needed": 18,
        "critical_threshold": 250,
        "status": false
      },
      "milk": {
        "type": "whole",
        "current": 650.0,
        "needed": 150,
        "critical_threshold": 1000,
        "status": false
      }
    }
  },
  "request_id": "275ceafa-59e7-4639-b35f-61234f2ec634",
  "client_type": "scheduler",
  "server_type": "validation",
  "timestamp": "2025-06-15T02:55:40.630261"
}
```

### Response Fields

- **passed**: true if all items can be made, false otherwise
- **details**: Per-drink breakdown of ingredient availability
- **status**: true if drink can be made, false if insufficient ingredients
- **current**: Current inventory level
- **needed**: Required amount for the drink
- **critical_threshold**: Minimum stock level threshold
- **status** (per ingredient): true if sufficient, false if insufficient

## Function 2: Update Inventory (update_inventory)

**Purpose**: Update inventory levels after ingredient consumption

**Client**: Scheduler and Dashboard Services

### Request Structure

```json
{
  "request_id": "594d9767-33b6-4e3e-a424-05ccf08f27d8",
  "client_type": "scheduler",
  "function_name": "update_inventory",
  "payload": {
    "ingredients": [
      {
        "espresso": {
          "type": "regular",
          "amount": 2
        }
      },
      {
        "milk": {
          "type": "whole",
          "amount": 150
        }
      },
      {
        "cup": {
          "type": "H9",
          "amount": 1
        }
      }
    ]
  }
}
```

### Alternative Format (with items)

```json
{
  "request_id": "7b3e9f2a-4d8c-4e1f-9a2b-3c4d5e6f7g8h",
  "client_type": "scheduler",
  "function_name": "update_inventory",
  "payload": {
    "items": [
      {
        "drink_name": "cappuccino",
        "size": "small",
        "cup_id": "H9",
        "temperature": "hot",
        "ingredients": {
          "espresso": {
            "type": "regular",
            "amount": 1
          },
          "milk": {
            "type": "whole",
            "amount": 150
          }
        }
      }
    ],
    "ingredients": [
      {
        "cup": {
          "type": "H9",
          "amount": 1
        }
      }
    ]
  }
}
```

### Response Structure

```json
{
  "passed": true,
  "details": {
    "coffee_beans": {
      "type": "regular",
      "updated_amount": -2,
      "status": "critical",
      "message": "Inventory critical level reached"
    },
    "milk": {
      "type": "whole",
      "updated_amount": -150,
      "status": "critical",
      "message": "Inventory critical level reached"
    },
    "cups": {
      "type": "H9",
      "updated_amount": -1,
      "status": "critical",
      "message": "Inventory critical level reached"
    }
  },
  "request_id": "594d9767-33b6-4e3e-a424-05ccf08f27d8",
  "client_type": "scheduler",
  "server_type": "validation",
  "timestamp": "2025-06-15T02:55:43.069346"
}
```

### Response Fields

- **passed**: true if update succeeded, false if failed
- **details**: Per-ingredient update results
- **updated_amount**: Amount changed
- **status**: Inventory level status ("full", "warning", "critical")
- **message**: Human-readable status message

### Important Notes

- **Scheduler requests**: Amounts are automatically subtracted in the validation
- **Dashboard requests**: Use positive values to add, negative to subtract

## Function 3: Ingredient Status (ingredient_status)

**Purpose**: Get the current inventory status for all or specific ingredients

**Client**: Dashboard Service

### Request Structure

```json
{
  "request_id": "275ceafa-59e7-4639-b35f-61234f2ec634",
  "client_type": "dashboard",
  "function_name": "ingredient_status"
}
```

### Response Structure

```json
{
  "request_id": "82e5edb2-38ff-4af4-959c-37d552086041",
  "client_type": "dashboard",
  "details": {
    "coffee_beans": {
      "regular": {
        "status": "empty",
        "current_amount": -35.0,
        "warning_threshold": 500,
        "critical_threshold": 250,
        "final_res": false
      },
      "decaf": {
        "status": "full",
        "current_amount": 2785.0,
        "warning_threshold": 300,
        "critical_threshold": 150,
        "final_res": true
      }
    },
    "cups": {
      "H9": {
        "status": "empty",
        "current_amount": 18.0,
        "warning_threshold": 50,
        "critical_threshold": 25,
        "final_res": false
      }
    },
    "milk": {
      "whole": {
        "status": "empty",
        "current_amount": 500.0,
        "warning_threshold": 2000,
        "critical_threshold": 1000,
        "final_res": false
      }
    },
    "syrup": {
      "vanilla": {
        "status": "empty",
        "current_amount": 100.0,
        "warning_threshold": 300,
        "critical_threshold": 150,
        "final_res": false
      }
    }
  },
  "server_type": "validation",
  "timestamp": "2025-06-15T02:55:44.633359"
}
```

### Response Fields

- **details**: Complete inventory details organized by ingredient type
- **status**: "high", "medium", or "low"
- **current_amount**: Current inventory level
- **warning_threshold**: Level at which warnings are triggered
- **critical_threshold**: Minimum acceptable level

## Inventory Status Levels

### Status Definitions (decide if it is based on percentage, or thresholds)

- **full**: current_amount >= warning_threshold
- **low**: critical_threshold <= current_amount < warning_threshold
- **empty**: current_amount < critical_threshold

## Function 3: Refill Ingredient (refill_ingredient)

**Purpose**: Refill to maximum for all or specific ingredients

**Client**: Dashboard Service

### Request Structure

```json
{
  "request_id": "1234567890",
  "client_type": "dashboard",
  "function_name": "refill_ingredient",
  "payload": {
    "ingredients": [
      {
        "ingredient_type": "espresso",
        "subtype": "regular"
      }
    ]
  }
}
```

### Response Structure

```json
{
  "passed": false,
  "details": {
    "coffee_beans": {
      "type": "regular",
      "status": "success",
      "message": "Inventory refilled successfully"
    },
    "milk": {
      "type": "oat",
      "status": "success",
      "message": "Inventory refilled successfully"
    }
  },
  "request_id": "1234567890",
  "client_type": "dashboard",
  "server_type": "validation",
  "timestamp": "2025-06-17T18:33:49.911232"
}
```

### Response Fields

- **Details**: Complete inventory details organized by ingredient type
- **Passed:** If refilled successfully for all

## Error Handling

### Invalid Request Format

```json
{
  "request_id": "invalid-request",
  "client_type": "scheduler",
  "passed": false,
  "error": "Unknown function: invalid_function_name"
}
```

### Processing Errors

```json
{
  "request_id": "error-request",
  "client_type": "scheduler",
  "passed": false,
  "details": {
    "error": "Error processing request: [detailed error message]"
  }
}
```

## Integration Examples

### Python Example (using Pika)

```python
import pika
import json

# Connect to RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# Note: Contact the validation team (Uzair and Mais) for the login details (username and password)

# Send pre-check request
message = {
    "request_id": "unique-id-123",
    "client_type": "scheduler",
    "function_name": "pre_check",
    "payload": {
        "items": [
            {
                "drink_name": "cappuccino",
                "cup_id": "H9",
                "ingredients": {
                    "espresso": {"type": "regular", "amount": 1},
                    "milk": {"type": "whole", "amount": 150}
                }
            }
        ]
    }
}

channel.basic_publish(
    exchange='',
    routing_key='validation_queue',
    body=json.dumps(message)
)

# Listen for response on scheduler_response_queue
```