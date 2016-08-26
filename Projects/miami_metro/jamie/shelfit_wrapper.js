javascript:
	void((function()
	{
		shelf_svr='http://servername/';
		var e=document.createElement('script');
		e.setAttribute('type','text/javascript');
		e.setAttribute('charset','UTF-8');
		e.setAttribute('src',shelf_svr+'mymedia/site_folder/js/shelfit_getshelf.js?r='+Math.random()*99999999);
		document.body.appendChild(e)
	})());