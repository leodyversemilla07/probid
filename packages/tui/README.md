# @probid/tui

Terminal UI package for probid.

Status: **extracted** — provides Rich-based display primitives and theme system.

## Features

- **Theme system** — `ThemeColors`, `ThemeStyles`, `apply_style()`, `panelize()`
- **Display helpers** — currency formatting, table creation, panel creation
- **Output helpers** — `print_header()`, `print_success()`, `print_warning()`, `print_error()`

## Usage

```python
from probid_tui import print_header, print_success, format_currency, create_table
from probid_tui.theme import colors, styles

# Print formatted output
print_header("Procurement Results")
print_success("Analysis complete")

# Format currency
amount = format_currency(1500000)  # "PHP 1.50M"

# Create tables
table = create_table(
    title="Notices",
    columns=("Ref No", "Title", "Amount"),
    column_styles=("cyan", "", "green"),
)
table.add_row("12905086", "Laptop Procurement", "PHP 1.50M")
```

## Testing

```bash
python3 -m unittest packages/tui/tests -v
```
