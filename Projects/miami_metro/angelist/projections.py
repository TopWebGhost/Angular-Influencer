__author__ = 'atulsingh'
import math

def get_revenue_till(rev, month):
    result = 0
    i = 0
    while i <= month:
        result += rev[i]
        i += 1
    return result

def projections():
    curr_val = 217
    curr_brn_rate = 33 # /mo
    curr_rv_rate = 1.757 # /mon
    num_months = 24
    growth_rates_mom = [0.4] #[0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 1]

    rev_in_future = {}

    for r in growth_rates_mom:

        i = 0
        vals = []
        j = curr_rv_rate
        while i < num_months:
            print j, r
            j += j*r
            vals.append(j)
            i += 1
        rev_in_future[r] = vals
        print "%r %r" % (r, rev_in_future[r])
    i = 0
    total_rev = 0
    while i < num_months:
        money_now = curr_val - (curr_brn_rate * (i+1))

        print "%d\t" % i,
        for r in growth_rates_mom:
            print "%.2f\t%.2f\t%.2f\t%.2f\t" % (rev_in_future[r][i], get_revenue_till(rev_in_future[r], i), curr_brn_rate * i, money_now + get_revenue_till(rev_in_future[r], i)),
        print "\n"
        i += 1