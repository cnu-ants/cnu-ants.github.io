---
layout: page
# title: Albums
permalink: /activities
comments: false
---

<!-- {% assign unofficial_albums = site.albums | where: "type", "Unofficial" | sort: "album_date" | reverse %} -->

{% assign study_albums = site.activities | where: "type", "Study" | sort: "album_date" %}
{% assign outing_albums = site.activities | where: "type", "Outing" | sort: "album_date" | reverse %}

{% assign members = site.members | where: "visible", "true" %}
{% assign gradmembers = site.members | where: "visible", "false" %}

<section class="featured-posts">
    <div class="section-title">
        <h1><span>Study</span></h1>
    </div>

    <div style="float:none;overflow:hidden">
    {% for album in study_albums %}
      <div style="margin-top: 40px;" class="section-title">
        <h2><span>{{album.name}}</span></h2>
      </div>
      {% assign images = album.images %}
      {% include album_image.html %}
      {% include album_content.html tags=album.tags people=album.people authors=album.authors card_date=album.card_date date=album.date description=album.description %}
    {% endfor %}
    </div>

</section>
