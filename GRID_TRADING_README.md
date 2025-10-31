# Grid Trading Algorithm

A comprehensive grid trading strategy implementation for range-bound markets. This system places buy and sell orders at preset intervals to capitalize on price oscillations, with automated risk controls.

## Features

### Core Functionality
- **Grid-Based Order Placement**: Automatically places buy and sell orders at predefined price levels
- **Range-Bound Market Optimization**: Designed specifically for sideways/oscillating markets
- **Automated Order Management**: Dynamically creates new orders as existing ones are filled
- **Position Tracking**: Real-time tracking of all open positions and their P&L

### Risk Controls
- **Stop Loss**: Automatically closes positions when loss exceeds configured threshold
- **Take Profit**: Locks in profits when gain reaches target percentage
- **Position Size Limits**: Enforces maximum position size per trade
- **Maximum Open Orders**: Limits total number of concurrent pending orders
- **Total Exposure Limit**: Controls overall capital at risk

### Analytics & Monitoring
- **Trade Statistics**: Win rate, profit/loss, trade count
- **Real-time P&L**: Unrealized and realized profit/loss tracking
- **Strategy State Export**: Save and load strategy configurations
- **Simulation Tools**: Backtest strategies with historical data

## Installation

The grid trading module requires only Python 3.6+ standard library. No external dependencies are needed.

```bash
# No installation required - just import the module
import grid_trading
```

## Quick Start

### Basic Usage

```python
from grid_trading import GridTradingStrategy, RiskControl

# Configure risk parameters
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

# Initialize the grid
orders = strategy.initialize_grid()
print(f"Created {len(orders)} initial orders")

# Update with market price
strategy.update_price(32500.0)

# Get statistics
stats = strategy.get_statistics()
print(f"Total Profit: ${stats['total_profit']:.2f}")
print(f"Win Rate: {stats['win_rate']:.2f}%")
```

### Running a Simulation

```python
from grid_trading import GridTradingSimulator, create_example_strategy

# Create a strategy
strategy = create_example_strategy()

# Create simulator
simulator = GridTradingSimulator(strategy)

# Run with price data
price_data = [30500, 31000, 32000, 31500, 30800, 31200]
results = simulator.run_simulation(price_data)
```

## Configuration

### Grid Parameters

- **symbol**: Trading pair identifier (e.g., "BTC/USD")
- **lower_bound**: Minimum price for grid range
- **upper_bound**: Maximum price for grid range
- **grid_levels**: Number of price levels in the grid
- **quantity_per_grid**: Amount to trade at each grid level

### Risk Control Parameters

- **max_position_size**: Maximum size for a single position (default: 1000.0)
- **stop_loss_percentage**: Stop loss trigger percentage (default: 5.0%)
- **take_profit_percentage**: Take profit trigger percentage (default: 10.0%)
- **max_open_orders**: Maximum concurrent pending orders (default: 20)
- **max_total_exposure**: Maximum total capital at risk (default: 10000.0)

## Grid Trading Strategy Explanation

### How It Works

1. **Grid Setup**: The strategy divides a price range into evenly spaced levels
2. **Order Placement**: 
   - Buy orders are placed at lower grid levels
   - Sell orders are placed at upper grid levels
3. **Order Execution**:
   - When price drops to a buy level, a position is opened
   - When price rises to a sell level, the position is closed for profit
4. **Grid Rebalancing**: New orders are automatically placed after fills
5. **Risk Management**: Positions are monitored and closed if stop-loss or take-profit is hit

### Best Use Cases

- **Range-bound markets**: When price oscillates within a defined range
- **Low volatility periods**: When price movements are predictable
- **Mean reversion strategies**: Capitalizing on price returning to average
- **Sideways consolidation**: During market indecision phases

### Risk Considerations

- **Trending markets**: Grid trading can underperform in strong trends
- **Breakout risk**: Price moving outside the grid range
- **Capital requirements**: Requires sufficient capital for multiple positions
- **Liquidity**: Works best in liquid markets with tight spreads

## API Reference

### Classes

#### GridTradingStrategy

Main class implementing the grid trading logic.

**Methods:**
- `initialize_grid()`: Set up initial buy/sell orders across grid levels
- `update_price(price)`: Process current market price and check for fills
- `get_statistics()`: Return trading statistics dictionary
- `stop_strategy()`: Stop strategy and close all positions
- `export_state()`: Export strategy configuration and state
- `save_to_file(filename)`: Save strategy state to JSON file

#### Order

Represents a trading order.

**Attributes:**
- `order_id`: Unique order identifier
- `order_type`: BUY or SELL
- `price`: Order price
- `quantity`: Order quantity
- `status`: PENDING, FILLED, or CANCELLED

#### Position

Represents an open trading position.

**Methods:**
- `get_pnl(current_price)`: Calculate profit/loss at current price
- `get_pnl_percentage(current_price)`: Calculate P&L percentage

#### RiskControl

Configuration for risk management parameters.

#### GridTradingSimulator

Backtesting tool for grid trading strategies.

**Methods:**
- `run_simulation(price_data, timestamps)`: Run strategy with historical data

## Example Output

```
Grid Trading Strategy Example
==================================================

Created strategy: GridTradingStrategy(symbol='BTC/USD', range=[30000.0, 35000.0], levels=10, active=False, trades=0, pnl=0.00)
Grid prices: ['$30000.00', '$30555.56', '$31111.11', '$31666.67', '$32222.22', '$32777.78', '$33333.33', '$33888.89', '$34444.44', '$35000.00']

Running simulation with 100 price points...
Initializing grid with 10 levels...
Created 9 initial orders

=== Simulation Complete ===
Total Trades: 34
Winning Trades: 17
Losing Trades: 0
Win Rate: 50.00%
Total Profit: $805.95
Unrealized PnL: $0.00
Open Positions: 0
Pending Orders: 9
```

## Testing

Run the comprehensive test suite:

```bash
python3 -m unittest test.py -v
```

All tests include:
- Order creation and management
- Position tracking and P&L calculation
- Grid initialization and order placement
- Risk control enforcement
- Stop-loss and take-profit triggers
- Strategy state management
- Simulation functionality

## Advanced Usage

### Custom Strategy Creation

```python
# Create a tight grid for scalping
scalping_strategy = GridTradingStrategy(
    symbol="ETH/USD",
    lower_bound=1800.0,
    upper_bound=1900.0,
    grid_levels=20,  # More levels = tighter grid
    quantity_per_grid=0.5,
    risk_control=RiskControl(
        stop_loss_percentage=2.0,  # Tight stop loss
        take_profit_percentage=5.0  # Quick profit taking
    )
)

# Create a wide grid for swing trading
swing_strategy = GridTradingStrategy(
    symbol="BTC/USD",
    lower_bound=25000.0,
    upper_bound=40000.0,
    grid_levels=8,  # Fewer levels = wider grid
    quantity_per_grid=0.2,
    risk_control=RiskControl(
        stop_loss_percentage=10.0,  # Wider stop loss
        take_profit_percentage=20.0  # Larger profit target
    )
)
```

### Monitoring Active Strategy

```python
# Check current status
stats = strategy.get_statistics()
print(f"Open Positions: {stats['open_positions']}")
print(f"Pending Orders: {stats['pending_orders']}")
print(f"Total Exposure: ${stats['total_exposure']:.2f}")
print(f"Unrealized P&L: ${stats['unrealized_pnl']:.2f}")

# Export current state for analysis
strategy.save_to_file("strategy_state.json")
```

### Emergency Stop

```python
# Stop strategy immediately
strategy.stop_strategy()
# This will:
# - Cancel all pending orders
# - Close all open positions
# - Mark strategy as inactive
```

## Performance Optimization

### Grid Spacing Considerations

- **Tight grids** (many levels, small spacing):
  - More frequent trades
  - Smaller profit per trade
  - Better for low volatility
  
- **Wide grids** (few levels, large spacing):
  - Less frequent trades
  - Larger profit per trade
  - Better for higher volatility

### Capital Allocation

Recommended capital allocation:
- Reserve at least 50% of total capital for grid orders
- Keep buffer for adverse price movements outside grid
- Don't exceed total exposure limits

## Troubleshooting

### Common Issues

1. **No trades executing**: 
   - Check if price is within grid bounds
   - Verify orders are pending (not cancelled)

2. **Too many open positions**:
   - Reduce grid levels
   - Increase grid spacing
   - Lower quantity_per_grid

3. **Frequent stop-loss triggers**:
   - Widen grid range to reduce position risk
   - Increase stop_loss_percentage
   - Consider if market is trending (not suitable for grid)

## License

This implementation is provided as-is for educational and commercial use.

## Contributing

Contributions are welcome! Areas for enhancement:
- Additional risk management strategies
- Integration with live trading APIs
- Advanced order types (limit, stop-limit)
- Machine learning for grid parameter optimization
- Multi-timeframe analysis

## Disclaimer

This software is for educational purposes. Always test thoroughly before using with real capital. Past performance does not guarantee future results. Trading involves risk of loss.
