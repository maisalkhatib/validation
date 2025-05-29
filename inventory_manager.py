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
        
    def load_inventory_rules(self):
        """Load static configuration from JSON file"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(current_dir, 'config', 'inventory_rules.json')
            
            with open(file_path, 'r') as file:
                self.inventory_rules = json.load(file)
                
        except Exception as e:
            self.logger.error(f"Error loading inventory rules: {e}")
            raise
    
    def load_inventory_data(self):
        """Load inventory data from database and merge with rules"""
        for ingredient_type, rules in self.inventory_rules.items():
            if "subtypes" not in rules:
                continue
                
            for subtype, limits in rules["subtypes"].items():
                # Get current amount from database
                db_data = self.db_client.get_inventory(ingredient_type, subtype)
                
                # Combine DB data with rules
                self.inventory_cache[ingredient_type][subtype] = {
                    "current_amount": db_data.get("current_amount", 0) if db_data else 0,
                    "threshold": limits["threshold"],
                    "max_capacity": limits["max_capacity"]
                }
    
    def get_current_count(self, ingredient_type: str, subtype: str) -> float:
        """Get current inventory count for an ingredient"""
        if ingredient_type in self.inventory_cache and subtype in self.inventory_cache[ingredient_type]:
            return self.inventory_cache[ingredient_type][subtype]["current_amount"]
        
        # If not in cache, try to load from DB
        db_data = self.db_client.get_inventory(ingredient_type, subtype)
        return db_data.get("current_amount", 0) if db_data else 0
    
    def validate_inventory(self, ingredient_type: str, subtype: str, amount: float) -> Tuple[bool, str]:
        """
        Validate if enough inventory is available and above threshold
        Returns: (is_valid, message)
        """
        # Convert shots to grams for coffee beans
        if ingredient_type == "coffee_beans":
            shot_to_grams = self.inventory_rules.get("coffee_beans", {}).get("shot_to_grams", {})
            amount = shot_to_grams.get(str(int(amount)), amount * 9)
        
        # Get current amount and threshold
        current_amount = self.get_current_count(ingredient_type, subtype)
        threshold = self.inventory_cache.get(ingredient_type, {}).get(subtype, {}).get("threshold", 0)
        
        # Check if we have enough
        if current_amount < amount:
            return False, f"Not enough {ingredient_type}:{subtype}. Need {amount}, have {current_amount}"
        
        # Check if we'll go below threshold after using this amount
        remaining = current_amount - amount
        if remaining < threshold:
            return False, f"Cannot use {amount} {ingredient_type}:{subtype}. Would go below threshold"
        
        return True, "OK"
    
    def update_inventory(self, ingredient_type: str, subtype: str, amount: float) -> bool:
        """Update (subtract) inventory after use"""
        # Convert shots to grams for coffee beans
        if ingredient_type == "coffee_beans":
            shot_to_grams = self.inventory_rules.get("coffee_beans", {}).get("shot_to_grams", {})
            amount = shot_to_grams.get(str(int(amount)), amount * 9)
        
        # Get current amount
        current_amount = self.get_current_count(ingredient_type, subtype)
        new_amount = current_amount - amount
        
        # Update database
        success = self.db_client.update_amount(ingredient_type, subtype, new_amount)
        
        if success:
            # Update cache
            if ingredient_type in self.inventory_cache and subtype in self.inventory_cache[ingredient_type]:
                self.inventory_cache[ingredient_type][subtype]["current_amount"] = new_amount
        
        return success
    
    def refill_inventory(self, ingredient_type: str, subtype: str) -> bool:
        """Refill inventory to maximum capacity"""
        # Get max capacity
        max_capacity = self.inventory_cache.get(ingredient_type, {}).get(subtype, {}).get("max_capacity")
        
        if not max_capacity:
            return False
        
        # Update database
        success = self.db_client.update_amount(ingredient_type, subtype, max_capacity)
        
        if success:
            # Update cache
            if ingredient_type in self.inventory_cache and subtype in self.inventory_cache[ingredient_type]:
                self.inventory_cache[ingredient_type][subtype]["current_amount"] = max_capacity
        
        return success