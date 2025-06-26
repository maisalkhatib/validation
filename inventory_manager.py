import json
import os
import logging
from typing import Tuple
from db_client import DatabaseClient
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to see all log levels
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class InventoryManager:
    def __init__(self, db_client):
        self.db_client = db_client
        self.logger = logging.getLogger(__name__)
        
        # Initialize caches
        self.inventory_rules = {}
        self.inventory_cache = {
            "coffee_beans": {},
            "cups": {},
            "milk": {},
            "syrup": {}
        }
        
        # Load configuration and inventory data
        self.load_inventory_rules()
        self.load_inventory_data()
        self.logger.info("InventoryManager initialized successfully")
        
    def load_inventory_rules(self):
        """Load static configuration from JSON file"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(current_dir, 'inventory_rules.json')
            
            with open(file_path, 'r') as file:
                self.inventory_rules = json.load(file)
            
            self.logger.info(f"Loaded inventory rules from {file_path}")
                
        except Exception as e:
            self.logger.error(f"Error loading inventory rules: {e}")
            raise
    
    def load_inventory_data(self):
        """Load inventory data from database and merge with rules"""
        try:
            for ingredient_type, rules in self.inventory_rules.items():

                # Skip if no subtypes (like for special rules)
                if "subtypes" not in rules:
                    continue
                    
                # Load each subtype
                for subtype, limits in rules["subtypes"].items():
                    # Get current amount from database
                    db_data = self.db_client.get_inventory(ingredient_type, subtype)
                    
                    # Combine DB data with rules
                    self.inventory_cache[ingredient_type][subtype] = {
                        "current_amount": db_data.get("current_amount", 0) if db_data else 0,
                        "last_updated": db_data.get("last_updated").isoformat() if db_data.get("last_updated") else datetime.now().isoformat(),
                        "warning_threshold": limits["warning_threshold"],
                        "critical_threshold": limits["critical_threshold"],
                        "max_capacity": limits["max_capacity"]
                    }
            self.logger.info(f"Loaded inventory data!")


        except Exception as e:
            self.logger.error(f"Error loading inventory data: {e}")
            raise

    def get_current_count(self, ingredient_type: str, subtype: str) -> float:
        """Get current inventory count for an ingredient"""
        try:
            if ingredient_type in self.inventory_cache and subtype in self.inventory_cache[ingredient_type]:
                return self.inventory_cache[ingredient_type][subtype]["current_amount"]
            
            # If not in cache, try to load from DB
            db_data = self.db_client.get_inventory(ingredient_type, subtype)
            return db_data.get("current_amount", 0) if db_data else 0
        
        except Exception as e:
            self.logger.error(f"Error getting inventory count for {ingredient_type}:{subtype}: {e}")
            return 0

    def convert_shots_to_grams(self, shots: int) -> float:
        """Convert coffee shots to grams"""
        shot_conversions = self.inventory_rules.get("coffee_beans", {}).get("shot_to_grams", {})
        
        # Convert int keys from JSON (JSON stores as strings)
        if isinstance(shot_conversions, dict):
            shot_conversions = {int(k) if k.isdigit() else k: v for k, v in shot_conversions.items()}
        
        # Return conversion or default (9g per shot)
        return shot_conversions.get(shots, shots * 9)
    
        
    def validate_inventory(self, ingredient_type: str, subtype: str, amount: float) -> bool:
        """
        Validate if enough inventory is above critical threshold
        Returns: (is_valid, message)
        """
        # Convert shots to grams for coffee beans
        if ingredient_type == "coffee_beans":
            converted_amount = self.convert_shots_to_grams(int(amount))
            self.logger.debug(f"Converted {int(amount)} shots to {converted_amount} grams")
        
        # Get current amount and threshold
        current_amount = self.get_current_count(ingredient_type, subtype)
        critical_threshold = self.inventory_cache.get(ingredient_type, {}).get(subtype, {}).get("critical_threshold", 0)
        warning_threshold = self.inventory_cache.get(ingredient_type, {}).get(subtype, {}).get("warning_threshold", 0)

        # NOTE: @MAIS there are some issues with this function hence not changing it for now
        ## the issue is that is that converted amount is only initialized when it's coffee beans
        ## so if the request is for milk or syrup, it will not have converted_amount

        # Discussion: this way or just current_amount < threshold?
        # Check if we'll go below threshold after using this amount
        remaining = current_amount - converted_amount
        if remaining < critical_threshold:
            return False
        
        return True
    
    def update_inventory(self, ingredient_type: str, subtype: str, amount: float) -> Tuple[bool, str]:
        """
        Update (subtract/add) inventory after use
        Returns: Tuple of (success_status, warning_status)
            - success_status: bool indicating if database update was successful
            - warning_status: str indicating if warning is needed ("warning" or "no_warning")
            NOTE: THIS function is never invoked if the amount can't be taken from the inventory
        """
        try:
            # Convert shots to grams for coffee beans
            if ingredient_type == "coffee_beans":
                amount = self.convert_shots_to_grams(int(amount))
            
            # Get current amount
            current_amount = self.get_current_count(ingredient_type, subtype)
            warning_threshold = self.inventory_cache.get(ingredient_type, {}).get(subtype, {}).get("warning_threshold", 0)
            critical_threshold = self.inventory_cache.get(ingredient_type, {}).get(subtype, {}).get("critical_threshold", 0)

            new_amount = current_amount + amount
            
            # Update database
            success = self.db_client.update_inventory(ingredient_type, subtype, new_amount)
            
            if success:
                # Update cache
                if ingredient_type in self.inventory_cache and subtype in self.inventory_cache[ingredient_type]:
                    self.inventory_cache[ingredient_type][subtype]["current_amount"] = new_amount
                
                self.logger.info(f"Updated {ingredient_type}:{subtype} from {current_amount} to {new_amount}")

                print(f"inside update_inventory: new_amount: {new_amount}, critical_threshold: {critical_threshold}, warning_threshold: {warning_threshold}")
                # changes_by_mais:
                # switch the order of the critical and warning
                if new_amount < critical_threshold:
                    return True, "critical"
                elif new_amount < warning_threshold:
                    return True, "warning"
                
                print(f"inside update_inventory: success: {success}, warning: no_warning")
            return success, "no_warning"
        
        except Exception as e:
            self.logger.error(f"Error updating inventory: {e}")
            return False, "no_warning"
        
    def refill_inventory(self, ingredient_type: str = None, subtype: str = None) -> bool:
        """Refill inventory to maximum capacity"""
        try:
            # Determine what to refill
            if ingredient_type is None and subtype is None:
                ingredient_types = list(self.inventory_cache.keys())
            elif ingredient_type is not None and subtype is None:
                if ingredient_type not in self.inventory_cache:
                    self.logger.error(f"Invalid ingredient type: {ingredient_type}")
                    return False
                ingredient_types = [ingredient_type]
            elif ingredient_type is not None and subtype is not None:
                if ingredient_type not in self.inventory_cache or subtype not in self.inventory_cache[ingredient_type]:
                    self.logger.error(f"Invalid ingredient type or subtype: {ingredient_type}:{subtype}")
                    return False
                ingredient_types = [ingredient_type]
            else:
                self.logger.error(f"Invalid input: {ingredient_type}:{subtype}")
                return False
            
            # Track overall success
            overall_success = True
            
            for ing_type in ingredient_types:
                # Determine subtypes to process
                if subtype is not None:
                    subtypes_to_process = [subtype]
                else:
                    subtypes_to_process = list(self.inventory_cache[ing_type].keys())
                
                for sub in subtypes_to_process:
                    # Get max capacity
                    max_capacity = self.inventory_cache.get(ing_type, {}).get(sub, {}).get("max_capacity")
                    
                    if not max_capacity:
                        self.logger.error(f"No max capacity found for {ing_type}:{sub}")
                        overall_success = False
                        continue
                    
                    # Update database
                    success = self.db_client.update_inventory(ing_type, sub, max_capacity)
                    
                    if success:
                        # Update cache
                        if ing_type in self.inventory_cache and sub in self.inventory_cache[ing_type]:
                            self.inventory_cache[ing_type][sub]["current_amount"] = max_capacity
                        self.logger.info(f"Refilled {ing_type}:{sub} to max capacity: {max_capacity}")
                    else:
                        overall_success = False
                        self.logger.error(f"Failed to refill {ing_type}:{sub}")
            
            return overall_success
            
        except Exception as e:
            self.logger.error(f"Error refilling inventory: {e}")
            return False

    def get_inventory_status(self, ingredient_type: str = None, subtype: str = None) -> dict:
        """
        Get inventory status with flexible filtering
        Returns hierarchical dict with percentage, amount, status, date
        """
        result = {}
        
        # Determine ingredient_types to process
        if ingredient_type is None:
            ingredient_types_to_process = self.inventory_cache.keys()
        
        elif ingredient_type and subtype is None:
            if ingredient_type not in self.inventory_cache:
                return {}
            ingredient_types_to_process = [ingredient_type]
        
        elif ingredient_type and subtype:
            if ingredient_type not in self.inventory_cache or subtype not in self.inventory_cache[ingredient_type]:
                return {}
            ingredient_types_to_process = [ingredient_type]
        
        else:
            return {}
        
        # Process ingredient_types
        for ing_type in ingredient_types_to_process:
            result[ing_type] = {}
            
            # Determine subtypes
            if subtype is not None:
                subtypes_to_process = [subtype]
            else:
                subtypes_to_process = self.inventory_cache[ing_type].keys()
            
            # Process each subtype
            for sub in subtypes_to_process:
                if sub in self.inventory_cache[ing_type]:
                    data = self.inventory_cache[ing_type][sub]
                    current_amount = data["current_amount"]
                    max_capacity = data["max_capacity"]
                    last_updated = data["last_updated"]
                    critical_threshold = data["critical_threshold"]
                    
                    # Calculate percentage
                    percentage = int(((current_amount - critical_threshold) / max_capacity) * 100) if max_capacity > 0 else 0
                    
                    # Get status using percentage-based rules
                    if percentage >= 66:
                        status = "high"
                    elif percentage >= 33:
                        status = "medium"
                    elif percentage >= 0:
                        status = "low"
                    else:
                        status = "empty"
                    
                    result[ing_type][sub] = {
                        "percentage": percentage,
                        "amount": current_amount,
                        "status": status,
                        "last_updated": last_updated
                    }
        
        return result
    
    def get_category_summary(self) -> dict:
        """
        Get lowest inventory level per category
        Returns dict with lowest item in each category, num of item in each category
        """
        category_summary = {}
        
        for ingredient_type, subtypes in self.inventory_cache.items():
            lowest_percentage = 100
            lowest_subtype = None
            lowest_data = None
            
            for subtype, data in subtypes.items():
                current_amount = data["current_amount"]
                max_capacity = data["max_capacity"]
                critical_threshold = data["critical_threshold"]
                
                # Calculate percentage (same formula as get_inventory_status)
                percentage = int(((current_amount - critical_threshold) / max_capacity) * 100) if max_capacity > 0 else 0
                
                if percentage < lowest_percentage:
                    lowest_percentage = percentage
                    lowest_subtype = subtype
                    lowest_data = data
            
            if lowest_data:
                # Determine status
                if lowest_percentage >= 66:
                    status = "high"
                elif lowest_percentage >= 33:
                    status = "medium"
                elif lowest_percentage >= 0:
                    status = "low"
                else:
                    status = "empty"
                
                category_summary[ingredient_type] = {
                    "lowest_subtype": lowest_subtype,
                    "percentage": lowest_percentage,
                    "amount": lowest_data["current_amount"],
                    "status": status,
                    "last_updated": lowest_data.get("last_updated", datetime.now().isoformat())
                }
            category_summary[ingredient_type]["items_count"] = len(subtypes)
        return category_summary
    
    def get_inventory_stock_level_stats(self) -> dict:
        """
        Get inventory statistics by severity level
        Returns count of items in each status category
        """
        stats = {
            "high": 0,
            "medium": 0,
            "low": 0,
            "empty": 0,
            "total": 0,
        }
        
        for ingredient_type, subtypes in self.inventory_cache.items():
            for subtype, data in subtypes.items():
                current_amount = data["current_amount"]
                max_capacity = data["max_capacity"]
                critical_threshold = data["critical_threshold"]
                
                # Calculate percentage
                percentage = int(((current_amount - critical_threshold) / max_capacity) * 100) if max_capacity > 0 else 0
                
                # Determine status and increment counters
                if percentage >= 66:
                    status = "high"
                    stats["high"] += 1
                elif percentage >= 33:
                    status = "medium"
                    stats["medium"] += 1
                elif percentage >= 0:
                    status = "low"
                    stats["low"] += 1
                else:
                    status = "empty"
                    stats["empty"] += 1                
                stats["total"] += 1
        
        print(f"Inventory stock level stats: {stats}")
        return stats



if __name__ == "__main__":
    # initialize the db client in the main validation: 
    db_client = DatabaseClient(
            "dbname=barns_inventory user=postgres password=QSS2030QSS host=localhost port=5432"
        )
    inventory_manager = InventoryManager(db_client)

    # inventory_status = inventory_manager.get_inventory_status()
    # print(f"Inventory status: {json.dumps(inventory_status, indent=2)}")
    # print("--------------------------------")

    # inventory_milk_status = inventory_manager.get_inventory_status(ingredient_type="milk")
    # print(f"Inventory milk status: {json.dumps(inventory_milk_status, indent=2)}")

    # print("--------------------------------")

    # inventory_whole_milk_status = inventory_manager.get_inventory_status(ingredient_type="milk", subtype="whole")
    # print(f"Inventory whole milk status: {json.dumps(inventory_whole_milk_status, indent=2)}")

    # print("--------------------------------")

    # inventory_regular_beans_status = inventory_manager.get_inventory_status(ingredient_type="coffee_beans", subtype="regular")
    # print(f"Inventory regular beans status: {json.dumps(inventory_regular_beans_status, indent=2)}")

    # print("--------------------------------")

    # inventory_category_summary = inventory_manager.get_category_summary()
    # print(f"Inventory category summary: {json.dumps(inventory_category_summary, indent=2)}")

    inventory_stock_level_stats = inventory_manager.get_inventory_stock_level_stats()
    print(f"Inventory stock level stats: {json.dumps(inventory_stock_level_stats, indent=2)}")



"""   
validate_inventory(ingredient_type, subtype, amount) → bool: 
    - Check if we have enough inventory
    parameters:
        ingredient_type: str -> "coffee_beans", "cups", "milk", "syrup"
        subtype: str ->Coffee beans: "regular", "decaf"
                        Cups: "H7", "H9", "H12", "C7", "C9", "C12", "C16"
                        Milk: "whole", "skim", "oat", "soy"
                        Syrup: "vanilla", "caramel", "hazelnut"
        amount: float -> amount of ingredient to use
                For coffee_beans: Number of shots (1, 2, or 3) - will be converted to grams automatically
                For cups: Always 1 (one cup at a time)
                For milk/syrup: Amount in milliliters (ml)
    returns:
        bool: True if we have enough inventory, False otherwise
    
    Example:
        is_valid = inventory_manager.validate_inventory("coffee_beans", "regular", 1)
        is_valid = inventory_manager.validate_inventory("cups", "H7", 1)
        
update_inventory(ingredient_type, subtype, amount) → Tuple[bool, str]:
    - Update inventory after use
    parameters: same as validate_inventory
    returns:
        Tuple[bool, str]:
            - success_status: bool indicating if database update was successful
            - warning_status: str indicating if warning to dashboard is needed ("warning" or "no_warning")
    - example:
        success, warning = inventory_manager.update_inventory("coffee_beans", "regular", 1)

refill_inventory(ingredient_type, subtype) → bool:
    - Refill inventory to maximum capacity
    parameters: same as validate_inventory
    returns:
        bool: True if inventory was refilled successfully, False otherwise
    - example:
        success = inventory_manager.refill_inventory("coffee_beans", "regular")
"""