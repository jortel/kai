package com.redhat.coolstore.service;

import jakarta.ejb.ActivationConfigProperty;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.jms.JMSException;
import jakarta.jms.Message;
import jakarta.jms.TextMessage;

import org.eclipse.microprofile.reactive.messaging.Incoming;

import com.redhat.coolstore.model.Order;
import com.redhat.coolstore.utils.Transformers;

@ApplicationScoped
public class OrderServiceMDB {

	@Inject
	OrderService orderService;

	@Inject
	CatalogService catalogService;

	@Incoming("topic/orders")
	public void onMessage(String orderStr) {
		System.out.println("\nMessage recd !");
		try {
			System.out.println("Received order: " + orderStr);
			Order order = Transformers.jsonToOrder(orderStr);
			System.out.println("Order object is " + order);
			orderService.save(order);
			order.getItemList().forEach(orderItem -> {
				catalogService.updateInventoryItems(orderItem.getProductId(), orderItem.getQuantity());
			});
		} catch (Exception e) {
			throw new RuntimeException(e);
		}
	}

}