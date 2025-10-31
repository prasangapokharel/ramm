"""
Grid Trading Algorithm for Range-Bound Markets

This module implements a grid trading strategy that places buy and sell orders
at preset price intervals to capitalize on price oscillations in range-bound markets.
Includes automated risk controls and position management.
"""

import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from enum import Enum
import json


class OrderType(Enum):
    """Order type enumeration"""
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    """Order status enumeration"""
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


class Order:
    """Represents a trading order in the grid"""
    
    def __init__(self, order_id: int, order_type: OrderType, price: float, 
                 quantity: float, timestamp: Optional[datetime] = None):
        self.order_id = order_id
        self.order_type = order_type
        self.price = price
        self.quantity = quantity
        self.timestamp = timestamp or datetime.now()
        self.status = OrderStatus.PENDING
        self.filled_price: Optional[float] = None
        self.filled_timestamp: Optional[datetime] = None
    
    def fill(self, filled_price: float):
        """Mark order as filled"""
        self.status = OrderStatus.FILLED
        self.filled_price = filled_price
        self.filled_timestamp = datetime.now()
    
    def cancel(self):
        """Cancel the order"""
        self.status = OrderStatus.CANCELLED
    
    def to_dict(self) -> Dict:
        """Convert order to dictionary"""
        return {
            'order_id': self.order_id,
            'order_type': self.order_type.value,
            'price': self.price,
            'quantity': self.quantity,
            'status': self.status.value,
            'timestamp': self.timestamp.isoformat(),
            'filled_price': self.filled_price,
            'filled_timestamp': self.filled_timestamp.isoformat() if self.filled_timestamp else None
        }


class Position:
    """Represents a trading position"""
    
    def __init__(self, quantity: float, entry_price: float, entry_time: Optional[datetime] = None):
        self.quantity = quantity  # Positive for long, negative for short
        self.entry_price = entry_price
        self.entry_time = entry_time or datetime.now()
    
    def get_pnl(self, current_price: float) -> float:
        """Calculate unrealized profit/loss"""
        return self.quantity * (current_price - self.entry_price)
    
    def get_pnl_percentage(self, current_price: float) -> float:
        """Calculate unrealized profit/loss percentage"""
        if self.entry_price == 0:
            return 0.0
        return ((current_price - self.entry_price) / self.entry_price) * 100
    
    def to_dict(self) -> Dict:
        """Convert position to dictionary"""
        return {
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time.isoformat()
        }


class RiskControl:
    """Risk control parameters for the grid trading strategy"""
    
    def __init__(self, 
                 max_position_size: float = 1000.0,
                 stop_loss_percentage: float = 5.0,
                 take_profit_percentage: float = 10.0,
                 max_open_orders: int = 20,
                 max_total_exposure: float = 10000.0):
        """
        Initialize risk control parameters
        
        Args:
            max_position_size: Maximum size for a single position
            stop_loss_percentage: Stop loss percentage (e.g., 5.0 for 5%)
            take_profit_percentage: Take profit percentage (e.g., 10.0 for 10%)
            max_open_orders: Maximum number of open orders allowed
            max_total_exposure: Maximum total exposure across all positions
        """
        self.max_position_size = max_position_size
        self.stop_loss_percentage = stop_loss_percentage
        self.take_profit_percentage = take_profit_percentage
        self.max_open_orders = max_open_orders
        self.max_total_exposure = max_total_exposure
    
    def to_dict(self) -> Dict:
        """Convert risk control to dictionary"""
        return {
            'max_position_size': self.max_position_size,
            'stop_loss_percentage': self.stop_loss_percentage,
            'take_profit_percentage': self.take_profit_percentage,
            'max_open_orders': self.max_open_orders,
            'max_total_exposure': self.max_total_exposure
        }


class GridTradingStrategy:
    """
    Grid Trading Strategy for range-bound markets
    
    This strategy places buy and sell orders at preset intervals within a price range
    to capitalize on price oscillations.
    """
    
    def __init__(self, 
                 symbol: str,
                 lower_bound: float,
                 upper_bound: float,
                 grid_levels: int,
                 quantity_per_grid: float,
                 risk_control: Optional[RiskControl] = None):
        """
        Initialize the grid trading strategy
        
        Args:
            symbol: Trading symbol (e.g., "BTC/USD")
            lower_bound: Lower price bound of the grid
            upper_bound: Upper price bound of the grid
            grid_levels: Number of grid levels between bounds
            quantity_per_grid: Quantity to trade at each grid level
            risk_control: Risk control parameters
        """
        if lower_bound >= upper_bound:
            raise ValueError("Lower bound must be less than upper bound")
        if grid_levels < 2:
            raise ValueError("Grid levels must be at least 2")
        if quantity_per_grid <= 0:
            raise ValueError("Quantity per grid must be positive")
        
        self.symbol = symbol
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.grid_levels = grid_levels
        self.quantity_per_grid = quantity_per_grid
        self.risk_control = risk_control or RiskControl()
        
        # Calculate grid spacing
        self.grid_spacing = (upper_bound - lower_bound) / (grid_levels - 1)
        
        # Initialize grid prices
        self.grid_prices = [
            lower_bound + i * self.grid_spacing 
            for i in range(grid_levels)
        ]
        
        # Order and position tracking
        self.orders: List[Order] = []
        self.positions: List[Position] = []
        self.next_order_id = 1
        
        # Statistics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0.0
        
        # Strategy state
        self.is_active = False
        self.current_price: Optional[float] = None
    
    def initialize_grid(self) -> List[Order]:
        """
        Initialize the grid by placing buy and sell orders at all grid levels
        
        Returns:
            List of created orders
        """
        orders = []
        
        for i, price in enumerate(self.grid_prices):
            # Place buy orders at lower levels
            if i < len(self.grid_prices) // 2:
                order = self._create_order(OrderType.BUY, price, self.quantity_per_grid)
                orders.append(order)
            # Place sell orders at upper levels
            elif i > len(self.grid_prices) // 2:
                order = self._create_order(OrderType.SELL, price, self.quantity_per_grid)
                orders.append(order)
        
        self.is_active = True
        return orders
    
    def _create_order(self, order_type: OrderType, price: float, quantity: float) -> Order:
        """Create a new order"""
        # Check risk controls
        if len(self.get_pending_orders()) >= self.risk_control.max_open_orders:
            raise RuntimeError(f"Maximum open orders limit reached: {self.risk_control.max_open_orders}")
        
        if quantity > self.risk_control.max_position_size:
            raise ValueError(f"Quantity {quantity} exceeds max position size {self.risk_control.max_position_size}")
        
        order = Order(self.next_order_id, order_type, price, quantity)
        self.orders.append(order)
        self.next_order_id += 1
        return order
    
    def update_price(self, current_price: float):
        """
        Update current market price and check for order fills
        
        Args:
            current_price: Current market price
        """
        self.current_price = current_price
        
        # Check if price is outside grid bounds
        if current_price < self.lower_bound or current_price > self.upper_bound:
            print(f"Warning: Price {current_price} is outside grid bounds [{self.lower_bound}, {self.upper_bound}]")
        
        # Process pending orders
        self._process_orders(current_price)
        
        # Check risk controls on existing positions
        self._check_risk_controls(current_price)
    
    def _process_orders(self, current_price: float):
        """Process pending orders based on current price"""
        for order in self.get_pending_orders():
            # Fill buy orders when price reaches or goes below order price
            if order.order_type == OrderType.BUY and current_price <= order.price:
                self._fill_order(order, current_price)
            # Fill sell orders when price reaches or goes above order price
            elif order.order_type == OrderType.SELL and current_price >= order.price:
                self._fill_order(order, current_price)
    
    def _fill_order(self, order: Order, filled_price: float):
        """
        Fill an order and create/update positions
        
        Args:
            order: Order to fill
            filled_price: Price at which order was filled
        """
        order.fill(filled_price)
        self.total_trades += 1
        
        # Create or update position
        if order.order_type == OrderType.BUY:
            self._open_position(order.quantity, filled_price)
            # Place a new sell order at the next grid level above
            self._place_next_sell_order(filled_price)
        else:  # SELL
            self._close_position(order.quantity, filled_price)
            # Place a new buy order at the next grid level below
            self._place_next_buy_order(filled_price)
    
    def _open_position(self, quantity: float, entry_price: float):
        """Open a new long position"""
        # Check total exposure
        total_exposure = self.get_total_exposure()
        new_exposure = quantity * entry_price
        
        if total_exposure + new_exposure > self.risk_control.max_total_exposure:
            print(f"Warning: Cannot open position. Would exceed max total exposure.")
            return
        
        position = Position(quantity, entry_price)
        self.positions.append(position)
    
    def _close_position(self, quantity: float, exit_price: float):
        """Close existing positions"""
        remaining_quantity = quantity
        
        for position in list(self.positions):
            if remaining_quantity <= 0:
                break
            
            if position.quantity > 0:  # Long position
                close_qty = min(position.quantity, remaining_quantity)
                pnl = close_qty * (exit_price - position.entry_price)
                
                self.total_profit += pnl
                if pnl > 0:
                    self.winning_trades += 1
                else:
                    self.losing_trades += 1
                
                position.quantity -= close_qty
                remaining_quantity -= close_qty
                
                # Remove position if fully closed
                if position.quantity == 0:
                    self.positions.remove(position)
    
    def _place_next_sell_order(self, current_price: float):
        """Place a sell order at the next grid level above current price"""
        for price in self.grid_prices:
            if price > current_price:
                try:
                    self._create_order(OrderType.SELL, price, self.quantity_per_grid)
                    break
                except RuntimeError:
                    # Max open orders reached
                    break
    
    def _place_next_buy_order(self, current_price: float):
        """Place a buy order at the next grid level below current price"""
        for price in reversed(self.grid_prices):
            if price < current_price:
                try:
                    self._create_order(OrderType.BUY, price, self.quantity_per_grid)
                    break
                except RuntimeError:
                    # Max open orders reached
                    break
    
    def _check_risk_controls(self, current_price: float):
        """Check risk controls on existing positions"""
        for position in list(self.positions):
            if position.quantity <= 0:
                continue
            
            pnl_percentage = position.get_pnl_percentage(current_price)
            
            # Check stop loss
            if pnl_percentage <= -self.risk_control.stop_loss_percentage:
                print(f"Stop loss triggered for position at {position.entry_price}. Closing position.")
                self._close_position(position.quantity, current_price)
            
            # Check take profit
            elif pnl_percentage >= self.risk_control.take_profit_percentage:
                print(f"Take profit triggered for position at {position.entry_price}. Closing position.")
                self._close_position(position.quantity, current_price)
    
    def get_pending_orders(self) -> List[Order]:
        """Get all pending orders"""
        return [order for order in self.orders if order.status == OrderStatus.PENDING]
    
    def get_filled_orders(self) -> List[Order]:
        """Get all filled orders"""
        return [order for order in self.orders if order.status == OrderStatus.FILLED]
    
    def get_total_exposure(self) -> float:
        """Calculate total exposure across all positions"""
        return sum(position.quantity * position.entry_price for position in self.positions)
    
    def get_unrealized_pnl(self) -> float:
        """Calculate total unrealized profit/loss"""
        if self.current_price is None:
            return 0.0
        return sum(position.get_pnl(self.current_price) for position in self.positions)
    
    def get_statistics(self) -> Dict:
        """Get trading statistics"""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0.0
        
        return {
            'symbol': self.symbol,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'total_profit': self.total_profit,
            'unrealized_pnl': self.get_unrealized_pnl(),
            'total_exposure': self.get_total_exposure(),
            'open_positions': len(self.positions),
            'pending_orders': len(self.get_pending_orders()),
            'current_price': self.current_price
        }
    
    def cancel_all_orders(self):
        """Cancel all pending orders"""
        for order in self.get_pending_orders():
            order.cancel()
    
    def close_all_positions(self, current_price: float):
        """Close all open positions at current price"""
        for position in list(self.positions):
            if position.quantity > 0:
                self._close_position(position.quantity, current_price)
    
    def stop_strategy(self):
        """Stop the strategy and clean up"""
        self.is_active = False
        self.cancel_all_orders()
        # Close all positions using a fallback price if current_price is not set
        closing_price = self.current_price if self.current_price else self.grid_prices[len(self.grid_prices) // 2]
        self.close_all_positions(closing_price)
    
    def export_state(self) -> Dict:
        """Export strategy state to dictionary"""
        return {
            'symbol': self.symbol,
            'lower_bound': self.lower_bound,
            'upper_bound': self.upper_bound,
            'grid_levels': self.grid_levels,
            'quantity_per_grid': self.quantity_per_grid,
            'grid_spacing': self.grid_spacing,
            'grid_prices': self.grid_prices,
            'is_active': self.is_active,
            'current_price': self.current_price,
            'risk_control': self.risk_control.to_dict(),
            'orders': [order.to_dict() for order in self.orders],
            'positions': [position.to_dict() for position in self.positions],
            'statistics': self.get_statistics()
        }
    
    def save_to_file(self, filename: str):
        """Save strategy state to JSON file"""
        state = self.export_state()
        with open(filename, 'w') as f:
            json.dump(state, f, indent=2)
    
    def __repr__(self):
        stats = self.get_statistics()
        return (f"GridTradingStrategy(symbol='{self.symbol}', "
                f"range=[{self.lower_bound}, {self.upper_bound}], "
                f"levels={self.grid_levels}, "
                f"active={self.is_active}, "
                f"trades={stats['total_trades']}, "
                f"pnl={stats['total_profit']:.2f})")


class GridTradingSimulator:
    """
    Simulator for backtesting grid trading strategies
    """
    
    def __init__(self, strategy: GridTradingStrategy):
        self.strategy = strategy
        self.price_history: List[Tuple[datetime, float]] = []
    
    def run_simulation(self, price_data: List[float], timestamps: Optional[List[datetime]] = None):
        """
        Run simulation with historical price data
        
        Args:
            price_data: List of historical prices
            timestamps: Optional list of timestamps for each price
        """
        if not timestamps:
            timestamps = [datetime.now() for _ in price_data]
        
        # Initialize grid
        print(f"Initializing grid with {len(self.strategy.grid_prices)} levels...")
        initial_orders = self.strategy.initialize_grid()
        print(f"Created {len(initial_orders)} initial orders")
        
        # Process each price point
        for timestamp, price in zip(timestamps, price_data):
            self.strategy.update_price(price)
            self.price_history.append((timestamp, price))
        
        # Print final statistics
        stats = self.strategy.get_statistics()
        print("\n=== Simulation Complete ===")
        print(f"Total Trades: {stats['total_trades']}")
        print(f"Winning Trades: {stats['winning_trades']}")
        print(f"Losing Trades: {stats['losing_trades']}")
        print(f"Win Rate: {stats['win_rate']:.2f}%")
        print(f"Total Profit: ${stats['total_profit']:.2f}")
        print(f"Unrealized PnL: ${stats['unrealized_pnl']:.2f}")
        print(f"Open Positions: {stats['open_positions']}")
        print(f"Pending Orders: {stats['pending_orders']}")
        
        return stats


def create_example_strategy() -> GridTradingStrategy:
    """
    Create an example grid trading strategy
    
    Returns:
        Configured GridTradingStrategy instance
    """
    # Configure risk controls
    risk_control = RiskControl(
        max_position_size=100.0,
        stop_loss_percentage=5.0,
        take_profit_percentage=10.0,
        max_open_orders=20,
        max_total_exposure=10000.0
    )
    
    # Create grid trading strategy
    strategy = GridTradingStrategy(
        symbol="BTC/USD",
        lower_bound=30000.0,
        upper_bound=35000.0,
        grid_levels=10,
        quantity_per_grid=0.1,
        risk_control=risk_control
    )
    
    return strategy


if __name__ == "__main__":
    # Example usage
    print("Grid Trading Strategy Example")
    print("=" * 50)
    
    # Create example strategy
    strategy = create_example_strategy()
    print(f"\nCreated strategy: {strategy}")
    print(f"Grid prices: {[f'${p:.2f}' for p in strategy.grid_prices]}")
    
    # Create simulator
    simulator = GridTradingSimulator(strategy)
    
    # Generate sample price data (oscillating within range)
    import random
    random.seed(42)
    
    base_price = 32500.0
    price_data = []
    for i in range(100):
        # Create oscillating price movement
        noise = random.uniform(-500, 500)
        trend = 300 * (i % 20 - 10) / 10  # Oscillating trend
        price = base_price + trend + noise
        # Keep within bounds (mostly)
        price = max(strategy.lower_bound - 200, min(strategy.upper_bound + 200, price))
        price_data.append(price)
    
    # Run simulation
    print("\nRunning simulation with 100 price points...")
    simulator.run_simulation(price_data)
    
    # Save strategy state
    strategy.save_to_file("/tmp/grid_strategy_state.json")
    print("\nStrategy state saved to /tmp/grid_strategy_state.json")
