import sys

PRICING_EC2_MICRO = 0.02
PRICING_EC2_SMALL = 0.08

CALCULATION_FREQUENCY_PER_DAY = [2, 4, 6, 8, 12, 24] # every 4 hours

num_items_per_user = [50, 100]#, 150, 200]

num_users = [100, 1000, 10000, 100000, 1000000]

OUR_CUT = 0.03 # 2$/100

AVERAGE_SALE = 100

''' Bandwidth cost '''
BW_IN = 0
BW_OUT_PER_GB = 0.12

''' Storage cost '''
STORE_TB = 0.125

PUT_REQUEST_COST = 0.00001
GET_REQUEST_COST = 0.00001


def bytes_per_user():
    # wishlist item: 18 fields
    # pricing results: 12
    # combination id: 7
    # Total: 37 fields
    # Each field is 4B, total = 150B
    return 150


def compute_cost_per_user_one_time(num_items):
    # based on our experience, we perform approx 1 task per min
    hour_per_task = 0.0167
    total_hours = hour_per_task * num_items
    
    cost_micro = total_hours * PRICING_EC2_SMALL
    
    return cost_micro


def compute_cost_per_user_per_day(num_items, frequency):
    
    total = compute_cost_per_user_one_time(num_items) * frequency
    
    return total

def sales_per_day_per_user():
    # 1 per month
    return 1.0/30.0

def storage_cost_per_user(num_items, frequency):
    total_bytes = (1024 + 20*frequency) * num_items
    rate = 0.125/1000000000.0
    
    storage_cost = total_bytes * rate
    return storage_cost
    
def bw_cost_per_user(num_items, frequency):
    total_bytes = 2048 * num_items * frequency
    rate = 0.12/1000000000.0
    
    bw_cost = total_bytes * rate
    return bw_cost

def put_get_cost_per_user(num_items, frequency):
    rate = 0.01/1000.0
    total_put_get = 2.0 * num_items * frequency
    
    put_get_cost = total_put_get * rate
    
    return put_get_cost

def compute_webserver_per_day(num_users):
    cost_per_hour = 0.05 # based on heroku
    cost_per_day_per_server = cost_per_hour * 24
    # each heroku can sustain 50 users
    num_servers = num_users/30
    
    total_cost_per_day = num_servers * cost_per_day_per_server
    
    return total_cost_per_day

def calculate_pay_cost():
    # 2 backend developers: $160K/year = 438$/day
    # 1 mobile = $150K/year = 410/day
    # 1 front-end = $150K/year = 410/day
    # 1 back-end = $150K/year = 410
    # co-founders = 2 * $150K/year = 821/day
    
    backend = (160000 + 150000)/365.0
    mobile = 150000/365
    front_end = 150000/365
    
    co_founders = 300000/365
    
    legal = 100000/365
    office = 100000/365
    
    marketing = 75000/365
    
    total_pay = co_founders + backend + mobile + front_end + legal + office + marketing
    
    return total_pay
    

if __name__ == "__main__":
    compute = compute_cost_per_user_per_day(100000, 1)
    storage = storage_cost_per_user(100000, 1)
    bw = bw_cost_per_user(100000, 1)
    for u in num_users:
#        for it in num_items_per_user:
#            compute = compute_cost_per_user_per_day(it, 6)
#            storage = storage_cost_per_user(it, 6)
#            bw = bw_cost_per_user(it, 6)
#            put_get_cost = put_get_cost_per_user(it, 6)
#            print "Compute " + str(compute) + " Storage " + str(storage) + " BW " + str(bw) + " PUT/GET " + str(put_get_cost)
#            cost1 = u * (compute + bw + storage + put_get_cost)
#            cost2 = u * (compute/2.0 + bw + storage + put_get_cost)
#            cost3 = u * (compute/3.0 + bw + storage + put_get_cost)
        sale1 = u * sales_per_day_per_user() * OUR_CUT * AVERAGE_SALE
        sale2 = u * sales_per_day_per_user() * OUR_CUT * AVERAGE_SALE/2.0
        webserver = compute_webserver_per_day(u)
        
        total_site_cost = compute + storage + bw + webserver
        total_pay = calculate_pay_cost()
        total = total_site_cost + total_pay
            #print " " + str(u) + " " + " " + str(it) + " " + str(cost1) + " " + str(sale1) + " " + str(cost2) + " " + str(sale2) + " " + str(cost3)
        print "Users: " + str(u) + " Revenue: " + str(sale1) + " Total Site Cost: " + str(total_site_cost) + " Total Pay: " + str(total_pay) + " Total " + str(total) + " Profit: " + str(sale1-total)
        
        
        
        