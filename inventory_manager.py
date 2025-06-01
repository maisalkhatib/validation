import json
import os
import logging
from typing import Tuple

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
            file_path = os.path.join(current_dir, 'config', 'inventory_rules.json')
            
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
                        "warning_threshold": limits["warning_threshold"],
                        "critical_threshold": limits["critical_threshold"],
                        "max_capacity": limits["max_capacity"]
                    }
            self.logger.info(f"Loaded inventory data for {len(self.inventory_cache)} ingredient types")
        
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
        
    def validate_inventory(self, ingredient_type: str, subtype: str, amount: float) -> bool:
        """
        Validate if enough inventory is above critical threshold
        Returns: (is_valid, message)
        """
        # Convert shots to grams for coffee beans
        if ingredient_type == "coffee_beans":
            amount = self.convert_shots_to_grams(int(amount))
            self.logger.debug(f"Converted {int(amount)} shots to {amount} grams")
        
        # Get current amount and threshold
        current_amount = self.get_current_count(ingredient_type, subtype)
        critical_threshold = self.inventory_cache.get(ingredient_type, {}).get(subtype, {}).get("critical_threshold", 0)
        

        # Discussion: this way or just current_amount < threshold?
        # Check if we'll go below threshold after using this amount
        remaining = current_amount - amount
        if remaining < critical_threshold:
            return False
        
        return True
    
    def update_inventory(self, ingredient_type: str, subtype: str, amount: float) -> Tuple[bool, str]:
        """
        Update (subtract) inventory after use
        Returns: Tuple of (success_status, warning_status)
            - success_status: bool indicating if database update was successful
            - warning_status: str indicating if warning is needed ("warning" or "no_warning")
        """
        try:
            # Convert shots to grams for coffee beans
            if ingredient_type == "coffee_beans":
                amount = self.convert_shots_to_grams(int(amount))
            
            # Get current amount
            current_amount = self.get_current_count(ingredient_type, subtype)
            warning_threshold = self.inventory_cache.get(ingredient_type, {}).get(subtype, {}).get("warning_threshold", 0)

            new_amount = current_amount - amount
            
            # Update database
            success = self.db_client.update_inventory(ingredient_type, subtype, new_amount)
            
            if success:
                # Update cache
                if ingredient_type in self.inventory_cache and subtype in self.inventory_cache[ingredient_type]:
                    self.inventory_cache[ingredient_type][subtype]["current_amount"] = new_amount
                
                self.logger.info(f"Updated {ingredient_type}:{subtype} from {current_amount} to {new_amount}")

                if new_amount < warning_threshold:
                    return True, "warning"
                
            return success, "no_warning"
        
        except Exception as e:
            self.logger.error(f"Error updating inventory: {e}")
            return False, "no_warning"
        
    def refill_inventory(self, ingredient_type: str, subtype: str) -> bool:
        """Refill inventory to maximum capacity"""
        try:
            # Get max capacity
            max_capacity = self.inventory_cache.get(ingredient_type, {}).get(subtype, {}).get("max_capacity")
            
            if not max_capacity:
                self.logger.error(f"No max capacity found for {ingredient_type}:{subtype}")
                return False
            
            # Update database
            success = self.db_client.update_inventory(ingredient_type, subtype, max_capacity)
            
            if success:
                # Update cache
                if ingredient_type in self.inventory_cache and subtype in self.inventory_cache[ingredient_type]:
                    self.inventory_cache[ingredient_type][subtype]["current_amount"] = max_capacity

                self.logger.info(f"Refilled {ingredient_type}:{subtype} to max capacity: {max_capacity}")
            return success
        
        except Exception as e:
            self.logger.error(f"Error refilling inventory: {e}")
            return False
        



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