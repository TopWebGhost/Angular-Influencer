#!/usr/bin/env ruby
require 'rubygems'
require 'active_record'

# create a class for employee records (the class is singular but the table is plural)
class Debra_Brands < ActiveRecord::Base
end

# connect to the database
ActiveRecord::Base.establish_connection(:adapter => 'postgresql',
                                        :host => 'localhost',
                                        :username => 'django_user',
                                        :password => 'mypassword',
                                        :database => 'devel_db');

table_a = ActiveRecord::Base.connection.tables
table_a.each do |l|
  if (l.index('_items') != nil) 
    item_cl_name_str = l.capitalize!
    puts item_cl_name_str
  end
  if (l.index('_brands') != nil) 
    brand_cl_name_str = l.capitalize!
    puts brand_cl_name_str
  end
end

brands = Debra_Brands.find(:all)
brands.each do |brand|
  puts brand.name
end
