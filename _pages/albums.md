---
layout: page
# title: Albums
permalink: /albums
comments: false
---

{% assign unofficial_albums = site.albums | where: "type", "Unofficial" | sort: "album_date" | reverse %}
{% assign official_albums = site.albums | where: "type", "Official" | sort: "album_date" | reverse %}

{% assign members = site.members | where: "visible", "true" %}
{% assign gradmembers = site.members | where: "visible", "false" %}

<section class="featured-posts">
    <div class="section-title">
        <h1><span>Official Albums</span></h1>
    </div>

    <div style="float:none;overflow:hidden">
    {% for album in official_albums %}
      <div style="margin-top: 40px;" class="section-title">
        <h2><span>{{album.name}}</span></h2>
      </div>
      {% assign images = album.images %}
      {% include album_image.html %}
    {% endfor %}
    </div>

</section>

<!-- <section class="featured-posts"> -->
<!--     <div class="section-title"> -->
<!--         <h1><span>Unofficial Albums</span></h1> -->
<!--     </div> -->
<!---->
<!--     <div style="float:none;overflow:hidden"> -->
<!--     {% for album in unofficial_albums %} -->
<!--       <div style="margin-top: 40px;" class="section-title"> -->
<!--         <h2><span>{{album.name}}</span></h2> -->
<!--       </div> -->
<!--       {% assign images = album.images %} -->
<!--       {% for image in images %} -->
<!--         {% include album_image.html %} -->
<!--       {% endfor %} -->
<!--     {% endfor %} -->
<!--     </div> -->
<!---->
<!-- </section> -->
