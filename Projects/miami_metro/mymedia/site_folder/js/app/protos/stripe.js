/**
 * Author: Bobby
 * Purpose: This file is loaded with any of our payment pages. Its primary function is as an abstraction layer to the
 * stripe library. It also provides some important handling of failure conditions.
 */


var stripe = {
    publish_key: null,
    payment_url: null,
    payment_amount: null,
    handler: null,

    init: function(publish_key, payment_url) {
        var _this = this;

        this.publish_key = publish_key;
        this.payment_url = payment_url;
        this.handler = StripeCheckout.configure({
            key: this.publish_key,
            image: '/mymedia/site_folder/images/global/shelf.png',
            token: function(token, args) {
                var deferred = $.post(payment_url, {
                    stripeToken: token['id'],
                    amount: _this.payment_amount
                });

                deferred.success(function(data) {
                    var parsed = $.parseJSON(data);
                    window.location = parsed['next'];
                });

                deferred.fail(function(data) {
                    var message_lb = LightBox.get_by_type('generic_message');
                    var error = Object.get_innermost($.parseJSON(data.responseText));

                    message_lb.set_message(error).set_title('Problem with payment');
                    message_lb.open();
                })
            }
        });

        return this;
    },

    open_handler: function(payment_name, payment_description, payment_amount) {
        this.payment_amount = payment_amount;

        // Open Checkout with further options
        this.handler.open({
          name: payment_name,
          description: payment_description,
          amount: payment_amount
        });
    }
};
