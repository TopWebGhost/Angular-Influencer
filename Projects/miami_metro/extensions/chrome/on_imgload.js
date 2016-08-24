/**********************************************
 * 
 * We have written our own method below: ImageLoadShelf 
 * This is in addition to the method that came with this plugin: ImageLoad
 * 
 */


/* Image adjust */
function ScaleImage(srcwidth, srcheight, targetwidth, targetheight, fLetterBox) {
    
    var result = { width: 0, height: 0, fScaleToTargetWidth: true };
    
    if ((srcwidth <= 0) || (srcheight <= 0) || (targetwidth <= 0) || (targetheight <= 0)) {
	return result;
    }
    
    // scale to the target width
    var scaleX1 = targetwidth;
    var scaleY1 = (srcheight * targetwidth) / srcwidth;
    
    // scale to the target height
    var scaleX2 = (srcwidth * targetheight) / srcheight;
    var scaleY2 = targetheight;
    
    // now figure out which one we should use
    var fScaleOnWidth = (scaleX2 > targetwidth);
    if (fScaleOnWidth) {
	fScaleOnWidth = fLetterBox;
    }
    else {
	fScaleOnWidth = !fLetterBox;
    }
    
    if (fScaleOnWidth) {
	result.width = Math.floor(scaleX1);
	result.height = Math.floor(scaleY1);
	result.fScaleToTargetWidth = true;
    }
    else {
	result.width = Math.floor(scaleX2);
	result.height = Math.floor(scaleY2);
	result.fScaleToTargetWidth = false;
    }
    result.targetleft = Math.floor((targetwidth - result.width) / 2);
    result.targettop = Math.floor((targetheight - result.height) / 2);
    
    return result;
}

/* Image adjust */
function OnImageLoad(evt) {
    
    var img = evt.currentTarget;
	
	var wli = ($(img).parent()).parent().width();
	//alert(($(img).parent()));
	//alert("width: " + wli);
	($(img).parent()).parent().css("height", wli);
	var hhh = ($(img).parent()).parent().height();
	//alert("height: " + hhh);
    
    // what's the size of this image and it's parent
    var w = $(img).width();
    var h = $(img).height();
    var tw = $(img).parent().width();
    var th = $(img).parent().height();
    //alert("width "+w + " height " + h + " tw " + tw + " th " + th);
    
    // compute the new size and offsets
    var result = ScaleImage(w, h, tw, th, false);
    
    
    
    // adjust the image coordinates and size
    img.width = result.width;
    img.height = result.height;
    $(img).css("left", result.targetleft);
    $(img).css("top", result.targettop);
}

/* Image adjust */
function OnImageLoadShelf(evt) {
    var img = evt.currentTarget;
	
	var wli = ($(img).parent().parent()).parent().width();
	($(img).parent().parent()).parent().css("height", wli);
    
    // what's the size of this image and it's parent
    var w = $(img).width();
    var h = $(img).height();
    var tw = $(img).parent().parent().width();
    var th = $(img).parent().parent().height();
    //alert("Input: (w=" + w + ", h=" + h + ") + pp's (w=" + tw + ", h=" + th + ")");
    // compute the new size and offsets
    var result = ScaleImage(w, h, tw, th, false);
    
    // adjust the image coordinates and size
    img.width = result.width;
    img.height = result.height;
    $(img).css("left", result.targetleft);
    $(img).css("top", result.targettop);
    //alert("Success! Input: (w=" + w + ",h=" + h + ") Ouput: (w=" + result.width + ", h=" + result.height + ")");
}
