# Development Guide

This guide covers development practices and patterns used in FynBus Chronicle.

## Project Structure

```
fynbus-chronicle/
├── chronicle/              # Django project settings
│   ├── settings/
│   │   ├── base.py        # Common settings
│   │   ├── dev.py         # Development settings
│   │   └── prod.py        # Production settings
│   ├── urls.py            # Root URL configuration
│   └── wsgi.py            # WSGI application
├── apps/
│   ├── logbook/           # Core logbook functionality
│   │   ├── models.py      # WeekLog, PriorityItem, Absence, Incident
│   │   ├── views.py       # HTMX views for inline CRUD
│   │   ├── admin.py       # Admin with inlines and exports
│   │   ├── forms.py       # Django forms
│   │   └── exports/       # PDF, Markdown, Email export modules
│   ├── accounts/          # Authentication
│   │   ├── views.py       # Custom login/logout
│   │   └── urls.py
│   └── dashboard/         # Dashboard views
│       └── views.py       # Dashboard and chart API
├── templates/             # Global templates
│   ├── base.html          # Base template with HTMX/Alpine
│   └── components/        # Reusable UI components
├── static/
│   ├── src/input.css      # Tailwind source
│   └── css/output.css     # Compiled Tailwind
└── docs/                  # Documentation
```

## Code Style

### Python

- Follow PEP 8
- Use type hints for function signatures
- Document modules, classes, and complex functions
- Code and comments in English

Example:

```python
def get_weeklog_stats(weeklog: WeekLog) -> dict[str, int]:
    """
    Calculate statistics for a week log.

    Args:
        weeklog: The WeekLog instance to analyze.

    Returns:
        Dictionary with ticket counts and delta.
    """
    return {
        "new": weeklog.helpdesk_new,
        "closed": weeklog.helpdesk_closed,
        "open": weeklog.helpdesk_open,
        "delta": weeklog.helpdesk_new - weeklog.helpdesk_closed,
    }
```

### Templates

- Use Tailwind CSS classes (no custom CSS unless necessary)
- Prefer component includes over duplication
- HTMX attributes for dynamic interactions

### JavaScript

- Minimal JavaScript; prefer HTMX + Alpine.js
- Chart.js for data visualization only

## HTMX Patterns

### Inline CRUD

The application uses HTMX for inline create/read/update/delete operations without full page reloads.

**Pattern: Adding items**

```html
<!-- Trigger button -->
<button hx-get="{% url 'logbook:priority-item-create' %}?weeklog={{ weeklog.id }}"
        hx-target="#priority-items-list"
        hx-swap="beforeend">
  Tilføj
</button>

<!-- List container -->
<div id="priority-items-list">
  {% for item in items %}
    {% include 'logbook/partials/priority_item_row.html' %}
  {% endfor %}
</div>
```

**Pattern: Inline editing**

```html
<!-- Row with edit/delete -->
<div id="item-{{ item.id }}" hx-target="this" hx-swap="outerHTML">
  {{ item.title }}
  <button hx-get="{% url 'logbook:priority-item-edit' item.pk %}">Edit</button>
  <button hx-delete="{% url 'logbook:priority-item-delete' item.pk %}"
          hx-confirm="Delete?">Delete</button>
</div>
```

**View pattern:**

```python
class PriorityItemCreateView(LoginRequiredMixin, CreateView):
    model = PriorityItem
    form_class = PriorityItemForm
    template_name = "logbook/partials/priority_item_form.html"

    def form_valid(self, form):
        form.instance.weeklog_id = self.request.GET.get("weeklog")
        self.object = form.save()
        return TemplateResponse(
            self.request,
            "logbook/partials/priority_item_row.html",
            {"item": self.object},
        )
```

### CSRF Token

The base template includes CSRF token for all HTMX requests:

```html
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
```

## Tailwind CSS

### Custom Components

Defined in `static/src/input.css`:

```css
@layer components {
  .btn-primary { @apply ...; }
  .card { @apply ...; }
  .input-field { @apply ...; }
}
```

### Color Palette

Scandinavian earth tones:
- `sand-*`: Primary neutral colors
- `sage-*`: Success/completed states
- `gold-*`: Warning/ongoing states
- `terracotta-*`: Error/blocked states

### Dark Mode

Uses class-based dark mode with Alpine.js:

```html
<html x-data="{ darkMode: localStorage.getItem('darkMode') === 'true' }"
      :class="{ 'dark': darkMode }">
```

## Adding New Features

### New Model

1. Create model in `apps/logbook/models.py`
2. Create form in `apps/logbook/forms.py`
3. Add admin configuration in `apps/logbook/admin.py`
4. Create views for CRUD operations
5. Create templates (row.html, form.html partials)
6. Add URL patterns
7. Run `python manage.py makemigrations && python manage.py migrate`

### New Dashboard Widget

1. Create view in `apps/dashboard/views.py`
2. Create partial template in `templates/dashboard/partials/`
3. Add URL for the partial
4. Add HTMX loader in dashboard index.html

## Testing

```bash
# Run all tests
pytest

# Run specific app tests
pytest apps/logbook/

# Run with coverage
pytest --cov=apps --cov-report=html
```

### Test Organization

```
apps/logbook/
├── tests/
│   ├── test_models.py
│   ├── test_views.py
│   ├── test_forms.py
│   └── test_exports.py
```

## Code Quality

```bash
# Format code
ruff format .

# Check linting
ruff check .

# Fix auto-fixable issues
ruff check --fix .
```

## Git Workflow

1. Create feature branch from main
2. Make changes with descriptive commits
3. Run tests and linting
4. Create pull request
5. Merge after review
