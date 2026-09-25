"""Run the catalog example through App('catalog_client')."""

# *** imports

# ** app
from tiferet import App, TiferetError

# *** functions

# ** function: show
def show(label, action):
    '''
    Print one feature result, or the catalog error message.

    :param label: The feature label to print.
    :type label: str
    :param action: A zero-arg callable that runs the feature.
    :type action: callable
    :return: The feature result, or None when the feature raised.
    :rtype: object
    '''

    # Run the feature and print either the result or the catalog error.
    try:
        result = action()
        print(f'{label}: {result}')
        return result
    except TiferetError as error:
        print(f'{label}: Error: {error.message}')
        return None

# Build the client from config.yml. Repositories are resolved by the app.
app = App('catalog_client')

# Add an item. A second run demonstrates the duplicate-sku rule.
show(
    'add',
    lambda: app.run('catalog.add_item', data=dict(sku='WIDGET-1', name='Widget', price=20.0)),
)

# List the current rows.
show('list', lambda: app.run('catalog.list_items', data={}))

# Replace the row with a discounted price.
show(
    'discount',
    lambda: app.run('catalog.apply_discount', data=dict(sku='WIDGET-1', discount=0.25)),
)

# Store labels on the group node, then read them back.
show(
    'save_meta',
    lambda: app.run('catalog.save_meta', data=dict(title='Workshop', currency='USD')),
)
show('get_meta', lambda: app.run('catalog.get_meta', data={}))

# Assert the item schema and reclaim deleted rows.
show('verify', lambda: app.run('catalog.verify_and_compact', data={}))

# Remove the item. This is the last feature so the file ends empty of rows.
show('remove', lambda: app.run('catalog.remove_item', data=dict(sku='WIDGET-1')))
