// facebook
// (function(d, s, id) {
//   var js, fjs = d.getElementsByTagName(s)[0];
//   if (d.getElementById(id)) return;
//   js = d.createElement(s); js.id = id;
//   js.src = "//connect.facebook.net/en_US/all.js#xfbml=1&appId={{ facebook_app_id }}";
//   fjs.parentNode.insertBefore(js, fjs);
// }(document, 'script', 'facebook-jssdk'));


//google fonts
WebFontConfig = {
  //google: { families: [ 'Raleway:400,200,100,300,500,600,700,800,900' ] }
  //google: { families: [ 'Oswald:400,300,700:latin' ] }
  //google: { families: [ 'PT+Sans+Narrow:400,700:latin' ] }
  //google: { families: [ 'Open+Sans::latin' ] }
  google: { families: [ 'Roboto:400,300,500,700,900,100:latin' ] }
  //google: { families: [ 'Libre+Baskerville:400,400italic,700:latin' ] }
  //google: { families: [ 'Roboto+Mono:400,100,300,500,700:latin' ] }
  //google: { families: [ 'Roboto+Condensed:400,300,700:latin' ] }
  //google: { families: [ 'Work+Sans:400,300,200,500,600,700:latin' ] }
};
(function() {
  var wf = document.createElement('script');
  wf.src = ('https:' == document.location.protocol ? 'https' : 'http') +
          '://ajax.googleapis.com/ajax/libs/webfont/1/webfont.js';
  wf.type = 'text/javascript';
  wf.async = 'true';
  var s = document.getElementsByTagName('script')[0];
  s.parentNode.insertBefore(wf, s);

})();
