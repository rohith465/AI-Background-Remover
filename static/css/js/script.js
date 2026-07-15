
const imageInput = document.getElementById("imageInput");

const previewImage = document.getElementById("previewImage");

if(imageInput){

imageInput.addEventListener("change",function(){

const file=this.files[0];

if(file){

previewImage.src=URL.createObjectURL(file);

}

});

}