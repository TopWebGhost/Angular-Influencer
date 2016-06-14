def startUp():
    from debra.constants import STRIPE_PLAN_STARTUP
    from debra.search_helpers import prepare_filter_params
    print "\nSearch page filters caching...\n"
    prepare_filter_params({}, plan_name=STRIPE_PLAN_STARTUP)
    print "\nSearch page filters caching... Done.\n"

def when_ready(server):
    import threading
    threading.Thread(target=startUp).start()
