Elastic Search integration docs
===============================

elastic_search_helpers.py
*************************
This file is divided in three sections:

- terms - those are wrappers around basic ES queries like „match phrase” or „term”.
- builders - used to create complete query out of building blocks
- runners - used to run queries and fetch results

Most important part is *builders* since it can change as integration with ES expands.

The idea behind ES helpers is to make small and easy dict with what we need from ES and translate it to actual query - so you don't have to think every time if you should use match phrase or other type of query in every case.  Each builder has array of *musts* and *shoulds* that needs to be added to query to make usable. For example if you are looking for data from particular blogger then you *must* add it to query, but then you are looking for some keyword in title or content so output *should* contain such in at least one of those fields. Shoulds and musts are joined together into bigger *bool* query. Other important part is pagination and ordering but it doesn't change too often - currently you can specify pagination but if you don't it will fall back into some defaults.

As result of *runners* we return 3 things: *Q* query that can be used in django orm filter, score mapping which is map between item (influencer, post, product) id and score as returned from ES. Last value is total hits used to list available pages or any other purposes.

In real life usage you will only use *runners* to get results.

Example:
We have "blog_name" field in index and we want to implement integration with influencers search. From index mapping we have to figure out that best query in this case would be "match phrase". We also assume that influencer *should* have that blog_name among other fields (but if it's only term then it will become must because there have to be at least one *should* satisfied). We have to decide what key will be used in simplified options dict - in this case lets use simply "blog_name". We figure out that only thing we need to implement in *builder* is adding new term to *shoulds* array when "blog_name" is present in options dict.  Finally piece of code to be added to influencer query builder looks like this:

.. code-block:: python

    if options.get("blog_name"):
        term = term_match_phrase("blog_name", options.get("blog_name"))
        shoulds.append(term)

If we also want to filter out posts to get only these which belongs to influencer with given "blog_name" we have to modify posts query builder and add following lines:

.. code-block:: python

    if options.get("blog_name"):
        term = term_match_phrase("blog_name", options.get("blog_name"))
        influencer_shoulds.append(term)

Please note that this time we modify *influencer_shoulds* array since this query is related to post's parent influencer and not directly to the post. Since we used same options key we can use same options dict to get different type of results.

search helpers, feed helpers and others
***************************************
Those modules are users of elastic search helpers. We pass filters from frontend to backend through json-serialized request body. Each usage involves building options dict which is less complicated than building whole query - it requires only adding those key-value pairs which are present in request. For example if user on influencers search page used "Blog name" search type and put some arbitrary string in input field (kept in variable *keyword*) we need to create following options dict:

.. code-block:: python

    options = {
        "blog_name": keyword
    }

Finally we use query runner to get results:

.. code-block:: python

    q, sm, _ = elastic_search_helpers.es_influencer_query_runner(options)
    influencers = influencers.filter(q)

(we skip total hits since its not used in this case). We use *q* to filter out influencers and then score mapping (*sm*) can be used to sort results.

important
*********

Currently searching of influencers is mix of elastic search queries and database filters so there is no way to implement pagination directly on ES. When all filter types will be implemented on elastic search we can use pagination options to divide results into pages without involving django paginator and other pricy operations.
