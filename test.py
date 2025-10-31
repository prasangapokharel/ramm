"""
Unit tests for the Grid Trading Strategy
"""

import unittest
from datetime import datetime
from grid_trading import (
    GridTradingStrategy, RiskControl, Order, Position, OrderType, OrderStatus,
    GridTradingSimulator, create_example_strategy
)


class TestOrder(unittest.TestCase):
    """Test cases for Order class"""
    
    def test_order_creation(self):
        """Test creating a new order"""
        order = Order(1, OrderType.BUY, 100.0, 1.0)
        self.assertEqual(order.order_id, 1)
        self.assertEqual(order.order_type, OrderType.BUY)
        self.assertEqual(order.price, 100.0)
        self.assertEqual(order.quantity, 1.0)
        self.assertEqual(order.status, OrderStatus.PENDING)
    
    def test_order_fill(self):
        """Test filling an order"""
        order = Order(1, OrderType.BUY, 100.0, 1.0)
        order.fill(99.5)
        self.assertEqual(order.status, OrderStatus.FILLED)
        self.assertEqual(order.filled_price, 99.5)
        self.assertIsNotNone(order.filled_timestamp)
    
    def test_order_cancel(self):
        """Test cancelling an order"""
        order = Order(1, OrderType.SELL, 105.0, 1.0)
        order.cancel()
        self.assertEqual(order.status, OrderStatus.CANCELLED)
    
    def test_order_to_dict(self):
        """Test order serialization"""
        order = Order(1, OrderType.BUY, 100.0, 1.0)
        order_dict = order.to_dict()
        self.assertEqual(order_dict['order_id'], 1)
        self.assertEqual(order_dict['order_type'], 'BUY')
        self.assertEqual(order_dict['price'], 100.0)


class TestPosition(unittest.TestCase):
    """Test cases for Position class"""
    
    def test_position_creation(self):
        """Test creating a new position"""
        position = Position(10.0, 100.0)
        self.assertEqual(position.quantity, 10.0)
        self.assertEqual(position.entry_price, 100.0)
        self.assertIsNotNone(position.entry_time)
    
    def test_position_pnl_profit(self):
        """Test profit calculation"""
        position = Position(10.0, 100.0)
        pnl = position.get_pnl(110.0)
        self.assertEqual(pnl, 100.0)  # 10 * (110 - 100)
    
    def test_position_pnl_loss(self):
        """Test loss calculation"""
        position = Position(10.0, 100.0)
        pnl = position.get_pnl(90.0)
        self.assertEqual(pnl, -100.0)  # 10 * (90 - 100)
    
    def test_position_pnl_percentage(self):
        """Test percentage profit/loss calculation"""
        position = Position(10.0, 100.0)
        pnl_pct = position.get_pnl_percentage(110.0)
        self.assertEqual(pnl_pct, 10.0)  # (110-100)/100 * 100


class TestRiskControl(unittest.TestCase):
    """Test cases for RiskControl class"""
    
    def test_risk_control_defaults(self):
        """Test default risk control parameters"""
        risk_control = RiskControl()
        self.assertEqual(risk_control.max_position_size, 1000.0)
        self.assertEqual(risk_control.stop_loss_percentage, 5.0)
        self.assertEqual(risk_control.take_profit_percentage, 10.0)
    
    def test_risk_control_custom(self):
        """Test custom risk control parameters"""
        risk_control = RiskControl(
            max_position_size=500.0,
            stop_loss_percentage=3.0,
            take_profit_percentage=8.0
        )
        self.assertEqual(risk_control.max_position_size, 500.0)
        self.assertEqual(risk_control.stop_loss_percentage, 3.0)
        self.assertEqual(risk_control.take_profit_percentage, 8.0)


class TestGridTradingStrategy(unittest.TestCase):
    """Test cases for GridTradingStrategy class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.risk_control = RiskControl(
            max_position_size=100.0,
            stop_loss_percentage=5.0,
            take_profit_percentage=10.0,
            max_open_orders=20
        )
        
        self.strategy = GridTradingStrategy(
            symbol="TEST/USD",
            lower_bound=100.0,
            upper_bound=200.0,
            grid_levels=5,
            quantity_per_grid=1.0,
            risk_control=self.risk_control
        )
    
    def test_strategy_initialization(self):
        """Test strategy initialization"""
        self.assertEqual(self.strategy.symbol, "TEST/USD")
        self.assertEqual(self.strategy.lower_bound, 100.0)
        self.assertEqual(self.strategy.upper_bound, 200.0)
        self.assertEqual(self.strategy.grid_levels, 5)
        self.assertEqual(len(self.strategy.grid_prices), 5)
    
    def test_grid_spacing(self):
        """Test grid spacing calculation"""
        expected_spacing = (200.0 - 100.0) / (5 - 1)
        self.assertEqual(self.strategy.grid_spacing, expected_spacing)
    
    def test_grid_prices(self):
        """Test grid price levels"""
        expected_prices = [100.0, 125.0, 150.0, 175.0, 200.0]
        self.assertEqual(self.strategy.grid_prices, expected_prices)
    
    def test_invalid_bounds(self):
        """Test invalid bound parameters"""
        with self.assertRaises(ValueError):
            GridTradingStrategy("TEST/USD", 200.0, 100.0, 5, 1.0)
    
    def test_invalid_grid_levels(self):
        """Test invalid grid levels"""
        with self.assertRaises(ValueError):
            GridTradingStrategy("TEST/USD", 100.0, 200.0, 1, 1.0)
    
    def test_initialize_grid(self):
        """Test grid initialization"""
        orders = self.strategy.initialize_grid()
        self.assertTrue(self.strategy.is_active)
        self.assertGreater(len(orders), 0)
        # Should have buy and sell orders
        buy_orders = [o for o in orders if o.order_type == OrderType.BUY]
        sell_orders = [o for o in orders if o.order_type == OrderType.SELL]
        self.assertGreater(len(buy_orders), 0)
        self.assertGreater(len(sell_orders), 0)
    
    def test_buy_order_fill(self):
        """Test buy order filling"""
        self.strategy.initialize_grid()
        initial_orders = len(self.strategy.orders)
        
        # Trigger a buy order at lower price
        self.strategy.update_price(110.0)
        
        filled_orders = self.strategy.get_filled_orders()
        self.assertGreater(len(filled_orders), 0)
    
    def test_sell_order_fill(self):
        """Test sell order filling"""
        # First open a position
        self.strategy._open_position(1.0, 150.0)
        
        # Place a sell order
        sell_order = self.strategy._create_order(OrderType.SELL, 160.0, 1.0)
        
        # Trigger the sell order
        self.strategy.update_price(160.0)
        
        self.assertEqual(sell_order.status, OrderStatus.FILLED)
    
    def test_position_opening(self):
        """Test opening a position"""
        initial_positions = len(self.strategy.positions)
        self.strategy._open_position(1.0, 150.0)
        self.assertEqual(len(self.strategy.positions), initial_positions + 1)
    
    def test_position_closing(self):
        """Test closing a position"""
        # Open a position
        self.strategy._open_position(1.0, 150.0)
        initial_count = len(self.strategy.positions)
        
        # Close the position
        self.strategy._close_position(1.0, 160.0)
        
        # Position should be removed
        self.assertEqual(len(self.strategy.positions), initial_count - 1)
    
    def test_profit_calculation(self):
        """Test profit calculation on closed position"""
        self.strategy._open_position(1.0, 100.0)
        self.strategy._close_position(1.0, 110.0)
        
        # Should have profit of 10
        self.assertEqual(self.strategy.total_profit, 10.0)
        self.assertEqual(self.strategy.winning_trades, 1)
    
    def test_loss_calculation(self):
        """Test loss calculation on closed position"""
        self.strategy._open_position(1.0, 100.0)
        self.strategy._close_position(1.0, 90.0)
        
        # Should have loss of -10
        self.assertEqual(self.strategy.total_profit, -10.0)
        self.assertEqual(self.strategy.losing_trades, 1)
    
    def test_stop_loss_trigger(self):
        """Test stop loss triggering"""
        # Open a position
        self.strategy._open_position(1.0, 100.0)
        self.assertEqual(len(self.strategy.positions), 1)
        
        # Drop price to trigger stop loss (5% loss)
        self.strategy.update_price(94.0)
        
        # Position should be closed
        self.assertEqual(len(self.strategy.positions), 0)
    
    def test_take_profit_trigger(self):
        """Test take profit triggering"""
        # Open a position
        self.strategy._open_position(1.0, 100.0)
        self.assertEqual(len(self.strategy.positions), 1)
        
        # Raise price to trigger take profit (10% gain)
        self.strategy.update_price(111.0)
        
        # Position should be closed
        self.assertEqual(len(self.strategy.positions), 0)
    
    def test_max_open_orders_limit(self):
        """Test maximum open orders limit"""
        # Create a strategy with low max orders
        risk_control = RiskControl(max_open_orders=2)
        strategy = GridTradingStrategy(
            symbol="TEST/USD",
            lower_bound=100.0,
            upper_bound=200.0,
            grid_levels=5,
            quantity_per_grid=1.0,
            risk_control=risk_control
        )
        
        # Create orders up to the limit
        strategy._create_order(OrderType.BUY, 110.0, 1.0)
        strategy._create_order(OrderType.BUY, 120.0, 1.0)
        
        # Next order should raise exception
        with self.assertRaises(RuntimeError):
            strategy._create_order(OrderType.BUY, 130.0, 1.0)
    
    def test_max_position_size_limit(self):
        """Test maximum position size limit"""
        # Attempt to create order exceeding max position size
        with self.assertRaises(ValueError):
            self.strategy._create_order(OrderType.BUY, 150.0, 200.0)
    
    def test_total_exposure_calculation(self):
        """Test total exposure calculation"""
        self.strategy._open_position(1.0, 100.0)
        self.strategy._open_position(2.0, 150.0)
        
        # Total exposure = 1*100 + 2*150 = 400
        self.assertEqual(self.strategy.get_total_exposure(), 400.0)
    
    def test_unrealized_pnl(self):
        """Test unrealized PnL calculation"""
        self.strategy._open_position(1.0, 100.0)
        self.strategy.current_price = 110.0
        
        # Unrealized PnL = 1 * (110 - 100) = 10
        self.assertEqual(self.strategy.get_unrealized_pnl(), 10.0)
    
    def test_get_statistics(self):
        """Test statistics retrieval"""
        self.strategy.initialize_grid()
        self.strategy.update_price(120.0)
        
        stats = self.strategy.get_statistics()
        self.assertIn('total_trades', stats)
        self.assertIn('winning_trades', stats)
        self.assertIn('win_rate', stats)
        self.assertIn('total_profit', stats)
    
    def test_cancel_all_orders(self):
        """Test cancelling all orders"""
        self.strategy.initialize_grid()
        pending_before = len(self.strategy.get_pending_orders())
        self.assertGreater(pending_before, 0)
        
        self.strategy.cancel_all_orders()
        pending_after = len(self.strategy.get_pending_orders())
        self.assertEqual(pending_after, 0)
    
    def test_close_all_positions(self):
        """Test closing all positions"""
        self.strategy._open_position(1.0, 100.0)
        self.strategy._open_position(1.0, 110.0)
        self.assertEqual(len(self.strategy.positions), 2)
        
        self.strategy.close_all_positions(120.0)
        self.assertEqual(len(self.strategy.positions), 0)
    
    def test_stop_strategy(self):
        """Test stopping the strategy"""
        self.strategy.initialize_grid()
        self.strategy._open_position(1.0, 150.0)
        
        self.strategy.stop_strategy()
        
        self.assertFalse(self.strategy.is_active)
        self.assertEqual(len(self.strategy.get_pending_orders()), 0)
        self.assertEqual(len(self.strategy.positions), 0)
    
    def test_export_state(self):
        """Test exporting strategy state"""
        self.strategy.initialize_grid()
        state = self.strategy.export_state()
        
        self.assertEqual(state['symbol'], 'TEST/USD')
        self.assertEqual(state['lower_bound'], 100.0)
        self.assertEqual(state['upper_bound'], 200.0)
        self.assertIn('statistics', state)
        self.assertIn('orders', state)
    
    def test_save_to_file(self):
        """Test saving strategy to file"""
        import tempfile
        import os
        
        self.strategy.initialize_grid()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            filename = f.name
        
        try:
            self.strategy.save_to_file(filename)
            self.assertTrue(os.path.exists(filename))
            
            # Verify file is valid JSON
            import json
            with open(filename, 'r') as f:
                data = json.load(f)
                self.assertEqual(data['symbol'], 'TEST/USD')
        finally:
            if os.path.exists(filename):
                os.remove(filename)


class TestGridTradingSimulator(unittest.TestCase):
    """Test cases for GridTradingSimulator class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.strategy = GridTradingStrategy(
            symbol="TEST/USD",
            lower_bound=100.0,
            upper_bound=200.0,
            grid_levels=5,
            quantity_per_grid=1.0
        )
        self.simulator = GridTradingSimulator(self.strategy)
    
    def test_simulator_creation(self):
        """Test simulator creation"""
        self.assertIsNotNone(self.simulator.strategy)
        self.assertEqual(len(self.simulator.price_history), 0)
    
    def test_run_simulation(self):
        """Test running a simulation"""
        price_data = [120.0, 130.0, 140.0, 130.0, 120.0]
        stats = self.simulator.run_simulation(price_data)
        
        self.assertIsNotNone(stats)
        self.assertIn('total_trades', stats)
        self.assertEqual(len(self.simulator.price_history), len(price_data))


class TestExampleStrategy(unittest.TestCase):
    """Test cases for example strategy creation"""
    
    def test_create_example_strategy(self):
        """Test creating example strategy"""
        strategy = create_example_strategy()
        
        self.assertIsNotNone(strategy)
        self.assertEqual(strategy.symbol, "BTC/USD")
        self.assertEqual(strategy.lower_bound, 30000.0)
        self.assertEqual(strategy.upper_bound, 35000.0)
        self.assertEqual(strategy.grid_levels, 10)


if __name__ == '__main__':
    unittest.main()
