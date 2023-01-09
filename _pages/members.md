---
layout: member
title: Members
permalink: /members
comments: true
---

{% assign members = site.members | where: "visible", "true" %}

<section class="featured-posts">
    <div class="section-title">
        <h2><span>Professor</span></h2>
    </div>
    
    <div style="float:none;overflow:hidden">
    {% for member in members %}
      {% assign position = member.position | downcase -%}
      {% if position == "professor" %}
        {% include memberbox.html %}
      {% endif %}
    {% endfor %}
    </div>
</section>

<section class="featured-posts">
    <div class="section-title">
        <h2><span>Graduate Students</span></h2>
    </div>
    
    <div style="float:none;overflow:hidden">
    {% assign members = members | sort: "startdate" %}
    {% for member in members %}
      {% assign position = member.position-display | downcase -%}
      {% if position == "ph.d. student" %}
        {% include memberbox.html %}
      {% endif %}
    {% endfor %}
    {% for member in members %}
      {% assign position = member.position-display | downcase -%}
      {% if position == "m.s. student" %}
        {% include memberbox.html %}
      {% endif %}
    {% endfor %}
    </div>
</section>

<section class="featured-posts">
    <div class="section-title">
        <h2><span>Undergraduate Students & Interns</span></h2>
    </div>
    
    <div style="float:none;overflow:hidden">
    {% assign members = members | sort: "startdate" %}
    {% for member in members %}
      {% assign position = member.position | downcase -%}
      {% if position == "undergraduate" %}
        {% include memberbox.html %}
      {% endif %}
    {% endfor %}
    </div>
</section>
