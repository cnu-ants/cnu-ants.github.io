---
layout: page
title: Publications
permalink: /publications
comments: false
---

{% assign range = (1..100) %}

{% assign all_members_eng = site.members | map: "name" | compact %}
{% assign all_members_kor = site.members | map: "name_kor" | compact %}

{% assign year = 2024 %}

{% for i in range %}
  {% if year == 2019 %}
    {% break %}
  {% endif %}

{% assign papers = site.papers | where: "year", year | sort: "month" | reverse %}

{% if papers.size > 0 %}
<section>
    <div class="section-title">
        <h2><span> {{ year }} </span></h2>
    </div>

    <div class="article-post">
<ul>
{% for p in papers %}
  <li>
    {% assign authors = "" %}
    {% if p.authors.size == 1 %}
      {% assign fst_author = p.authors | first %}
      {% assign fst_author_wo_star = fst_author | remove: "*" %}
      {% if all_members_eng contains fst_author_wo_star or all_members_kor contains fst_author_wo_star %}
        {% assign authors = fst_author | prepend:"<b>" | append:"</b>" %}
      {% else %}
        {% assign authors = fst_author %}
      {% endif %}
    {% elsif p.authors.size == 2 %}
      {% assign fst_author = p.authors | first %}
      {% assign fst_author_wo_star = fst_author | remove: "*" %}
      {% if all_members_eng contains fst_author_wo_star or all_members_kor contains fst_author_wo_star %}
        {% assign fst_author = fst_author | prepend:"<b>" | append:"</b>" %}
      {% else %}
        {% assign fst_author = fst_author %}
      {% endif %}
      {% assign sndauthor = p.authors | last %}
      {% assign sndauthor_wo_star = sndauthor | remove: "*" %}
      {% if all_members_eng contains sndauthor_wo_star or all_members_kor contains sndauthor_wo_star %}
        {% assign sndauthor = sndauthor | prepend:"<b>" | append:"</b>" %}
      {% else %}
        {% assign sndauthor = sndauthor %}
      {% endif %}
      {% assign authors = fst_author | append: " and " | append: sndauthor %}
    {% else %}
      {% for author in p.authors %}
        {% assign author_wo_star = author | remove: "*" %}
        {% if all_members_eng contains author_wo_star or all_members_kor contains author_wo_star %}
          {% assign author_re = author | prepend:"<b>" | append:"</b>" %}
        {% else %}
          {% assign author_re = author %}
        {% endif %}
        {% if forloop.first %}
          {% assign authors = author_re %}
        {% elsif forloop.last %}
          {% assign authors = authors | append: ", and " | append: author_re %}
        {% else %}
          {% assign authors = authors | append: ", " | append: author_re %}
        {% endif %}
      {% endfor %}
    {% endif %}
  {{ authors }}, "{{ p.title }}," <i> In {{ p.venue }}</i>,
  {% if p.moreinfo %}
    {{ p.moreinfo }}
  {% endif %}
  {% if p.status %}
    {{ p.status }}
  {% else %}
    {% if p.month %}
      {% case p.month %}
        {% when 1 %}
          January
        {% when 2 %}
          February
        {% when 3 %}
          March
        {% when 4 %}
          April
        {% when 5 %}
          May
        {% when 6 %}
          June
        {% when 7 %}
          July
        {% when 8 %}
          August
        {% when 9 %}
          September
        {% when 10 %}
          October
        {% when 11 %}
          November
        {% when 12 %}
          December
      {% endcase %}
    {% endif %}
    {{ p.year }}
  {% endif %}
  {% if p.award %} <b><i>{{ p.award }} </i></b> {% endif %}
  {% if p.remark %} <b><i>({{ p.remark}})</i></b> {% endif %}
  </li>
{% endfor %}
</ul>
</div>
</section>
{% endif %}
{% assign year = year | minus: 1 %}

{% endfor %} 

<section>
    <div class="section-title">
        <h2><span>Before 2020</span></h2>
    </div>

    <div class="article-post">
<ul>
{% assign year = 2019 %}
{% for i in range %}
{% if year == 2013 %}
{% break %}
{% endif %}
{% assign papers = site.papers | where: "year", year | sort: "month" | reverse %}
{% for p in papers %}
  <li>
    {% assign authors = "" %}
    {% if p.authors.size == 1 %}
      {% assign fst_author = p.authors | first %}
      {% if all_members_eng contains fst_author or all_members_kor contains fst_author %}
        {% assign authors = fst_author | prepend:"<b>" | append:"</b>" %}
      {% else %}
        {% assign authors = fst_author %}
      {% endif %}
    {% elsif p.authors.size == 2 %}
      {% assign fst_author = p.authors | first %}
      {% if all_members_eng contains fst_author or all_members_kor contains fst_author %}
        {% assign fst_author = fst_author | prepend:"<b>" | append:"</b>" %}
      {% else %}
        {% assign fst_author = fst_author %}
      {% endif %}
      {% assign snd_author = p.authors | last %}
      {% if all_members_eng contains snd_author or all_members_kor contains snd_author %}
        {% assign snd_author = snd_author | prepend:"<b>" | append:"</b>" %}
      {% else %}
        {% assign snd_author = snd_author %}
      {% endif %}
      {% assign authors = fst_author | append: " and " | append: snd_author %}
    {% else %}
      {% for author in p.authors %}
        {% if all_members_eng contains author or all_members_kor contains author %}
          {% assign author_re = author | prepend:"<b>" | append:"</b>" %}
        {% else %}
          {% assign author_re = author %}
        {% endif %}
        {% if forloop.first %}
          {% assign authors = author_re %}
        {% elsif forloop.last %}
          {% assign authors = authors | append: ", and " | append: author_re %}
        {% else %}
          {% assign authors = authors | append: ", " | append: author_re %}
        {% endif %}
      {% endfor %}
    {% endif %}
  {{ authors }}, "{{ p.title }}," <i> In {{ p.venue }}</i>, 
  {% if p.moreinfo %}
    {{ p.moreinfo }},
  {% endif %}
  {% if p.month %}
    {% case p.month %}
      {% when 1 %}
        January
      {% when 2 %}
        February
      {% when 3 %}
        March
      {% when 4 %}
        April
      {% when 5 %}
        May
      {% when 6 %}
        June
      {% when 7 %}
        July
      {% when 8 %}
        August
      {% when 9 %}
        September
      {% when 10 %}
        October
      {% when 11 %}
        November
      {% when 12 %}
        December
    {% endcase %}
  {% endif %}
  {{ p.year }}
  {% if p.award %} <b><i>{{ p.award }} </i></b> {% endif %}
  </li>
{% endfor %}
{% assign year = year | minus: 1 %}
{% endfor %} 
</ul>
</div>
</section>
