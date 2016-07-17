from bulk_update.helper import bulk_update

def migrate_clickmeter_product_links():
    from debra.models import BrandJobPost, Contract
    campaigns = BrandJobPost.objects.filter(
        candidates__contract__tracking_link__isnull=False).distinct()
    total = campaigns.count()
    for n, campaign in enumerate(campaigns, start=1):
        print '* {}/{} -- {} processing'.format(n, total, campaign)
        contracts = Contract.objects.filter(influencerjobmapping__job=campaign)
        if campaign.info_json.get('same_product_url'):
            product_url = campaign.info_json.get('product_url')
            if product_url:
                campaign.product_urls = [product_url]
            campaign.product_urls.append("")
            # campaign._ignore_old = True
            campaign.save()
        else:
            for contract in contracts:
                if contract.product_url:
                    contract.product_urls = [contract.product_url]
                contract.product_urls.append("")

                contract.product_tracking_links = [contract.tracking_link]
                contract._ignore_old = True
            bulk_update(
                contracts,
                update_fields=['product_urls', 'product_tracking_links'])
